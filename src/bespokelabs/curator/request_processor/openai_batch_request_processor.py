import asyncio
import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import Callable

import glob
import os
import litellm
from openai import AsyncOpenAI
from openai.types import Batch
from tqdm import tqdm

from bespokelabs.curator.dataset import Dataset
from bespokelabs.curator.prompter.prompt_formatter import PromptFormatter
from bespokelabs.curator.request_processor.base_request_processor import (
    BaseRequestProcessor,
    GenericRequest,
    GenericResponse,
    parse_response_message,
)
from bespokelabs.curator.request_processor.event_loop import run_in_event_loop
from bespokelabs.curator.request_processor.generic_response import TokenUsage

logger = logging.getLogger(__name__)

MAX_REQUESTS_PER_BATCH = 50_000
MAX_BYTES_PER_BATCH = 200 * 1024 * 1024

# NOTE(Ryan): This allows us to stay under the rate limit when submitting ~1,000 batches at a time
# When submitting >1,000 batches the batch submission and batch download operations get rate limited
MAX_CONCURRENT_BATCH_OPERATIONS = 100
MAX_RETRIES_PER_OPERATION = 5


class OpenAIBatchRequestProcessor(BaseRequestProcessor):
    def __init__(
        self,
        batch_size: int,
        model: str,
        delete_successful_batch_files: bool,
        delete_failed_batch_files: bool,
        temperature: float | None = None,
        top_p: float | None = None,
        batch_check_interval: int = 60,
        url: str = "https://api.openai.com/v1/chat/completions",
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
    ):
        if batch_size > MAX_REQUESTS_PER_BATCH:
            raise ValueError(
                f"batch_size {batch_size} is greater than the maximum of "
                f"{MAX_REQUESTS_PER_BATCH:,} requests per batch that OpenAI supports. "
                f"Please set your batch_size to be less than or equal to {MAX_REQUESTS_PER_BATCH:,}."
            )
        super().__init__(batch_size)
        self.model = model
        self.url: str = url
        self.check_interval: int = batch_check_interval
        self.temperature: float | None = temperature
        self.top_p: float | None = top_p
        self.presence_penalty: float | None = presence_penalty
        self.frequency_penalty: float | None = frequency_penalty
        self.delete_successful_batch_files: bool = delete_successful_batch_files
        self.delete_failed_batch_files: bool = delete_failed_batch_files

    def get_rate_limits(self) -> dict:
        """
        Function to get rate limits for a given annotator. Not available via response headers, so
        the following is based on tier 5 limits on Nov 6th, 2024.

        These rate limits vary per model
        and are determined by your organization's usage tier. View the following:
        https://platform.openai.com/docs/guides/rate-limits/usage-tiers
        https://platform.openai.com/settings/organization/limits

        Args:
            model (str): The model for which to get the rate limits.
            request_url (str): The request URL for which to get the rate limits.

        Returns:
            tuple[int, int]: A tuple containing the maximum number of requests and tokens per minute.
        """
        model_tpd = {
            "gpt-3.5-turbo": 5_000_000_000,
            "gpt-3.5-turbo-0125": 5_000_000_000,
            "gpt-3.5-turbo-1106": 5_000_000_000,
            "gpt-3.5-turbo-16k": 5_000_000_000,
            "gpt-3.5-turbo-instruct": 200_000,
            "gpt-3.5-turbo-instruct-0914": 200_000,
            "gpt-4": 150_000_000,
            "gpt-4-0613": 150_000_000,
            "gpt-4-turbo": 300_000_000,
            "gpt-4o": 10_000_000_000,
            "gpt-4o-mini": 15_000_000_000,
        }

        if self.model not in model_tpd:
            tpd = 1_000_000_000
        else:
            tpd = model_tpd[self.model]

        logger.info(f"Automatically set max_tokens_per_day to {tpd}, model: {self.model} ")

        rate_limits = {"max_tokens_per_day": tpd}

        return rate_limits

    def create_api_specific_request(self, generic_request: GenericRequest) -> dict:
        """
        Creates an API-specific request body from a generic request body.

        This function transforms a GenericRequest into the format expected by OpenAI's batch API.
        It handles both standard requests and those with JSON schema response formats.

        Args:
            generic_request (GenericRequest): The generic request object containing model, messages,
                and optional response format.

        Returns:
            dict: API specific request body formatted for OpenAI's batch API, including:
                - custom_id: String identifier from the original row index
                - method: Always "POST"
                - url: OpenAI chat completions endpoint
                - body: Request parameters including model, messages, and optional formatting
        """
        # NOTE(Ryan): We can have a shared place that creates the body (since it is the same for both openai online and batch).
        if generic_request.response_format:
            body = {
                "model": generic_request.model,
                "messages": generic_request.messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        # NOTE(Ryan): we are not using strict: True
                        "name": "output_schema",
                        "schema": generic_request.response_format,
                    },
                },
            }
        else:
            body = {
                "model": generic_request.model,
                "messages": generic_request.messages,
            }

        if self.temperature is not None:
            body["temperature"] = self.temperature

        if self.top_p is not None:
            body["top_p"] = self.top_p

        if self.presence_penalty is not None:
            body["presence_penalty"] = self.presence_penalty

        if self.frequency_penalty is not None:
            body["frequency_penalty"] = self.frequency_penalty

        request = {
            "custom_id": str(generic_request.original_row_idx),
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
        }

        return request

    async def requests_from_generic_request_file(self, request_file: str) -> list[dict]:
        """
        Reads and converts generic requests from a file into API-specific request format.

        Args:
            request_file (str): Path to the file containing generic requests in JSONL format.

        Returns:
            list[dict]: List of API-specific request bodies ready for batch submission.
        """
        api_specific_requests = []

        with open(request_file, "r") as file:
            for line in file:
                request = GenericRequest.model_validate_json(line.strip())
                api_specific_request = self.create_api_specific_request(request)
                api_specific_requests.append(json.dumps(api_specific_request))

        return api_specific_requests

    async def generic_response_file_from_responses(
        self, responses: str, batch: Batch, response_file: str
    ) -> str | None:
        request_file = batch.metadata["request_file_name"]
        generic_request_map = {}
        batch_created_at = datetime.datetime.fromtimestamp(batch.created_at)
        with open(request_file, "r") as f:
            for line in f:
                generic_request = GenericRequest.model_validate_json(line)
                generic_request_map[generic_request.original_row_idx] = generic_request

        with open(response_file, "w") as f:
            for raw_response in responses.text.splitlines():
                raw_response = json.loads(raw_response)
                request_idx = int(raw_response["custom_id"])
                generic_request = generic_request_map[request_idx]

                if raw_response["response"]["status_code"] != 200:
                    logger.warning(
                        f"Request {generic_request} failed with status code {raw_response['response']['status_code']}"
                    )
                    generic_response = GenericResponse(
                        response_message=None,
                        response_errors=[
                            f"Request {generic_request} failed with status code {raw_response['response']['status_code']}"
                        ],
                        raw_response=raw_response,
                        raw_request=None,
                        generic_request=generic_request,
                        created_at=batch_created_at,
                        finished_at=datetime.datetime.now(),
                        token_usage=None,
                        response_cost=None,
                    )
                else:
                    response_body = raw_response["response"]["body"]
                    choices = response_body["choices"]
                    usage = response_body.get("usage", {})

                    token_usage = TokenUsage(
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                    )

                    # Calculate cost using litellm (50% off for batch)
                    cost = (
                        litellm.completion_cost(
                            model=generic_request.model,
                            prompt=str(generic_request.messages),
                            completion=choices[0]["message"]["content"],
                        )
                        * 0.5
                    )

                    response_message = choices[0]["message"]["content"]
                    response_message, response_errors = parse_response_message(
                        response_message, self.prompt_formatter.response_format
                    )

                    generic_response = GenericResponse(
                        response_message=response_message,
                        response_errors=response_errors,
                        raw_response=raw_response,
                        raw_request=None,
                        generic_request=generic_request,
                        created_at=batch_created_at,
                        finished_at=datetime.datetime.now(),
                        token_usage=token_usage,
                        response_cost=cost,
                    )
                json.dump(generic_response.model_dump(), f, default=str)
                f.write("\n")

    def run(
        self,
        dataset: Dataset | None,
        working_dir: str,
        parse_func_hash: str,
        prompt_formatter: PromptFormatter,
    ) -> Dataset:
        """
        Processes a dataset using OpenAI's batch API.

        This function orchestrates the complete batch processing workflow:
        1. Attempts to load cached results if available
        2. Creates request files from the dataset
        3. Submits and processes batches
        4. Creates output dataset files

        Args:
            dataset (Dataset | None): Input dataset to process.
            working_dir (str): Directory for storing intermediate files and results.
            parse_func_hash (str): Hash of the parsing function for cache identification.
            prompt_formatter (PromptFormatter): Formatter for processing prompts and responses.

        Returns:
            Dataset: Processed dataset

        Raises:
            RuntimeError: If batch processing fails or no successful responses are received.
        """
        # load from already completed dataset
        output_dataset = self.attempt_loading_cached_dataset(working_dir, parse_func_hash)
        if output_dataset is not None:
            return output_dataset

        request_files = set(self.create_request_files(dataset, working_dir, prompt_formatter))

        batch_manager = BatchManager(
            working_dir,
            self.check_interval,
            prompt_formatter,
            delete_successful_batch_files=self.delete_successful_batch_files,
            delete_failed_batch_files=self.delete_failed_batch_files,
        )

        run_in_event_loop(
            batch_manager.submit_batches_from_request_files(
                request_files, self.requests_from_generic_request_file
            )
        )
        self.prompt_formatter = prompt_formatter
        run_in_event_loop(
            batch_manager.poll_and_process_batches(self.generic_response_file_from_responses)
        )

        return self.create_dataset_files(working_dir, parse_func_hash, prompt_formatter)

    def cancel_batches(self, working_dir: str) -> Dataset:
        """
        Cancels all submitted batches and exits the program.

        Args:
            working_dir (str): The directory where submitted batch object file is stored.
        """
        batch_manager = BatchManager(
            working_dir,
            self.check_interval,
            delete_successful_batch_files=self.delete_successful_batch_files,
            delete_failed_batch_files=self.delete_failed_batch_files,
        )

        run_in_event_loop(batch_manager.cancel_batches())
        logger.warning("Exiting program after batch cancellation.")
        os._exit(1)


@dataclass
class BatchStatusTracker:
    # total number of request files
    n_total_batches: int = 0
    unsubmitted_request_files: set[str] = field(default_factory=set)

    submitted_batch_ids: set[str] = field(default_factory=set)
    finished_batch_ids: set[str] = field(default_factory=set)
    downloaded_batch_ids: set[str] = field(default_factory=set)

    n_total_requests: int = 0
    # requests are in one of these two states
    n_finished_requests: int = 0
    n_downloaded_requests: int = 0

    batch_id_to_request_file_name: dict[str, str] = field(default_factory=dict)

    @property
    def n_unsubmitted_request_files(self) -> int:
        """Number of request files that haven't been submitted yet."""
        return len(self.unsubmitted_request_files)

    @property
    def n_submitted_batch_ids(self) -> int:
        """Number of batch IDs that have been submitted but not finished."""
        return len(self.submitted_batch_ids)

    @property
    def n_finished_batch_ids(self) -> int:
        """Number of batch IDs that have finished but not been downloaded."""
        return len(self.finished_batch_ids)

    @property
    def n_downloaded_batch_ids(self) -> int:
        """Number of batch IDs that have been downloaded."""
        return len(self.downloaded_batch_ids)

    def mark_as_submitted(self, request_file: str, batch_object: Batch):
        """Mark a request file as submitted."""
        assert request_file in self.unsubmitted_request_files
        self.unsubmitted_request_files.remove(request_file)
        self.submitted_batch_ids.add(batch_object.id)
        self.n_total_batches += 1
        self.n_total_requests += batch_object.request_counts.total
        logger.debug(f"Marked {request_file} as submitted with batch ID {batch_object.id}")

    def mark_as_finished(self, batch_object: Batch):
        """Mark a batch as finished."""
        if batch_object.id in self.submitted_batch_ids:
            self.submitted_batch_ids.remove(batch_object.id)
            self.finished_batch_ids.add(batch_object.id)
            self.n_finished_requests += (
                batch_object.request_counts.completed + batch_object.request_counts.failed
            )
            logger.debug(f"Marked batch ID {batch_object.id} as finished")

    def mark_as_downloaded(self, batch_object: Batch):
        """Mark a batch as downloaded."""
        if batch_object.id in self.finished_batch_ids:
            self.finished_batch_ids.remove(batch_object.id)
            self.downloaded_batch_ids.add(batch_object.id)
            n_requests = batch_object.request_counts.completed + batch_object.request_counts.failed
            self.n_downloaded_requests += n_requests
            self.n_finished_requests -= n_requests
            logger.debug(f"Marked batch ID {batch_object.id} as downloaded")

    def __str__(self) -> str:
        """Returns a human-readable string representation of the batch status."""
        status_lines = [
            f"Total batches: {self.n_total_batches}",
            f"Unsubmitted files: {self.n_unsubmitted_request_files}",
            f"Submitted batches: {self.n_submitted_batch_ids}",
            f"Finished batches: {self.n_finished_batch_ids}",
            f"Downloaded batches: {self.n_downloaded_batch_ids}",
            "",
            f"Total requests: {self.n_total_requests}",
            f"Finished requests: {self.n_finished_requests}",
            f"Downloaded requests: {self.n_downloaded_requests}",
        ]
        return "\n".join(status_lines)


def request_file_to_response_file(request_file: str, working_dir: str) -> str:
    """
    Converts a request file path to its corresponding response file path.

    Args:
        request_file (str): Path to the request file (e.g., "requests_0.jsonl")
        working_dir (str): Working directory containing the files

    Returns:
        str: Path to the corresponding response file (e.g., "responses_0.jsonl")
    """
    request_file_idx = request_file.split("/")[-1].split("_", 1)[1]
    return f"{working_dir}/responses_{request_file_idx}"


def response_file_to_request_file(response_file: str, working_dir: str) -> str:
    """
    Converts a response file path to its corresponding request file path.

    Args:
        response_file (str): Path to the response file (e.g., "responses_0.jsonl")
        working_dir (str): Working directory containing the files

    Returns:
        str: Path to the corresponding request file (e.g., "requests_0.jsonl")
    """
    response_file_idx = response_file.split("/")[-1].split("_", 1)[1]
    return f"{working_dir}/requests_{response_file_idx}"


async def requests_from_api_specific_request_file(self, request_file: str) -> list[dict]:
    with open(request_file, "r") as file:
        return file.read().splitlines()


async def api_specific_response_file_from_responses(
    responses: str, batch: Batch, response_file: str
) -> str | None:
    open(response_file, "w").write(responses.text)


class BatchManager:
    def __init__(
        self,
        working_dir: str,
        check_interval: int = 60,
        prompt_formatter: PromptFormatter | None = None,
        delete_successful_batch_files: bool = False,
        delete_failed_batch_files: bool = False,
    ) -> None:
        """Initialize BatchManager to handle OpenAI batch processing operations.

        Args:
            working_dir (str): Directory for storing batch-related files including requests, responses,
                and tracking files.
            check_interval (int): Time interval (in seconds) between batch status checks.
            prompt_formatter (PromptFormatter): Formatter used to process prompts and validate responses.
            delete_successful_batch_files (bool): Whether to delete input/output files from OpenAI
                after successful batch completion.
            delete_failed_batch_files (bool): Whether to delete input/error files from OpenAI
                after batch failure.
        """
        self.client = AsyncOpenAI()
        self.check_interval = check_interval
        self.working_dir = working_dir
        self.tracker = BatchStatusTracker()
        self.prompt_formatter = prompt_formatter
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCH_OPERATIONS)
        self.delete_successful_batch_files = delete_successful_batch_files
        self.delete_failed_batch_files = delete_failed_batch_files
        self._submitted_batch_objects_file_lock = asyncio.Lock()
        self._downloaded_batch_objects_file_lock = asyncio.Lock()
        self.submitted_batch_objects_file = (
            f"{working_dir}/batch_objects_submitted_{self.client.api_key[-4:]}.jsonl"
        )
        self.downloaded_batch_objects_file = (
            f"{working_dir}/batch_objects_downloaded_{self.client.api_key[-4:]}.jsonl"
        )
        self.batch_submit_pbar: tqdm | None = None
        self.request_pbar: tqdm | None = None

    async def create_batch_file(self, api_specific_requests: list[dict]) -> str:
        """
        Creates a batch file from a list of API-specific requests.

        Args:
            api_specific_requests (list[dict]): List of API-specific request bodies

        Returns:
            str: The encoded file content ready for upload

        Raises:
            ValueError: If the batch file contains more requests than OpenAI supports
        """
        n_requests = len(api_specific_requests)
        if n_requests > MAX_REQUESTS_PER_BATCH:
            raise ValueError(
                f"Batch file contains {n_requests:,} requests, "
                f"which is more than the maximum of {MAX_REQUESTS_PER_BATCH:,} requests per batch that OpenAI supports. "
                f"Preventing batch submission. Please reduce `batch_size`."
            )

        # Join requests with newlines and encode to bytes for upload
        file_content = "\n".join(api_specific_requests).encode()
        file_content_size = len(file_content)
        logger.debug(
            f"Batch file content size: {file_content_size / (1024*1024):.2f} MB ({file_content_size:,} bytes)"
        )
        if file_content_size > MAX_BYTES_PER_BATCH:
            raise ValueError(
                f"Batch file content size {file_content_size:,} bytes "
                f"is greater than the maximum of {MAX_BYTES_PER_BATCH:,} bytes per batch that OpenAI supports. "
                f"Please reduce your batch size or request content size (via prompt_func and response_format)."
            )
        return file_content

    async def upload_batch_file(self, file_content: bytes) -> str:
        """
        Uploads a batch file to OpenAI and waits until ready.

        Args:
            file_content (bytes): The encoded file content to upload

        Returns:
            str: The uploaded file object from OpenAI
        """
        try:
            batch_file_upload = await self.client.files.create(file=file_content, purpose="batch")
        except Exception as e:
            logger.error(f"Error uploading batch file: {e}")
            raise e

        # When submitting a file, sometimes the file is not ready immediately for status checking
        # Which results in a file not found error, so we briefly pause before checking the status
        await asyncio.sleep(1)

        try:
            batch_file_upload = await self.client.files.wait_for_processing(batch_file_upload.id)
        except Exception as e:
            logger.error(f"Error waiting for batch file to be processed: {e}")
            raise e

        logger.debug(f"File uploaded with id {batch_file_upload.id}")

        return batch_file_upload

    async def create_batch(self, batch_file_id: str, metadata: dict) -> Batch:
        """
        Creates a batch job with OpenAI using an uploaded file.

        Args:
            batch_file_id (str): ID of the uploaded file to use for the batch
            metadata (dict): Metadata to be included with the batch

        Returns:
            Batch: The created batch object from OpenAI

        Raises:
            Exception: If batch creation fails
        """
        try:
            batch_object = await self.client.batches.create(
                input_file_id=batch_file_id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
                metadata=metadata,
            )
            logger.debug(f"Batch submitted with id {batch_object.id}")
        except Exception as e:
            logger.error(f"Error submitting batch: {e}")
            raise e
        return batch_object

    async def submit_batch(self, requests: list[dict], metadata: dict) -> Batch:
        """
        Handles the complete batch submission process.

        Args:
            requests (list[dict]): List of API-specific requests to submit
            metadata (dict): Metadata to be included with the batch

        Returns:
            Batch: The created batch object from OpenAI

        Side Effects:
            - Updates tracker with submitted batch status
            - Appends batch object to submitted_batch_objects_file
        """
        async with self.semaphore:
            file_content = await self.create_batch_file(requests)
            batch_file_upload = await self.upload_batch_file(file_content)
            batch_object = await self.create_batch(batch_file_upload.id, metadata)

            # Simplified file writing
            with open(self.submitted_batch_objects_file, "a") as f:
                json.dump(batch_object.model_dump(), f, default=str)
                f.write("\n")
                f.flush()

            self.tracker.n_total_requests += len(requests)
            self.tracker.submitted_batch_ids.add(batch_object.id)

            return batch_object

    async def cancel_batches(self):
        if not os.path.exists(self.submitted_batch_objects_file):
            logger.warning("No batches to be cancelled, but cancel_batches=True.")
        else:
            logger.info(f"Batch objects file exists, cancelling all batches.")
            batch_ids = []
            with open(self.submitted_batch_objects_file, "r") as f:
                for line in f:
                    batch_obj = json.loads(line.strip())
                    batch_ids.append(batch_obj["id"])
            tasks = [self.cancel_batch(batch_id) for batch_id in batch_ids]
            results = await asyncio.gather(*tasks)
            failed = abs(sum(results))
            logger.warning(
                f"{len(results)-failed:,} out of {len(results):,} batches successfully cancelled"
            )
            logger.info(
                f"Moving batch objects file to {self.submitted_batch_objects_file}.cancelled"
            )
            os.rename(
                self.submitted_batch_objects_file, f"{self.submitted_batch_objects_file}.cancelled"
            )

    async def retrieve_batch(self, batch_id: str) -> Batch:
        try:
            batch_object = await self.client.batches.retrieve(batch_id)
        except Exception as e:
            logger.error(f"Error checking previously submitted batch: {e}")
            raise e
        return batch_object

    async def cancel_batch(self, batch_id: str) -> int:
        async with self.semaphore:
            batch_object = await self.retrieve_batch(batch_id)
            if batch_object.status == "completed":
                logger.warning(f"Batch {batch_id} is already completed, cannot cancel")
                return 0
            try:
                await self.client.batches.cancel(batch_id)
                logger.info(f"Successfully cancelled batch: {batch_id}")
                return 0
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to cancel batch {batch_id}: {error_msg}")
                return -1

    async def submit_batch_from_request_file(
        self,
        request_file: str,
        requests_from_request_file_func: Callable = requests_from_api_specific_request_file,
    ):
        """
        Submits a batch from a request file.

        Args:
            request_file (str): Path to the file containing requests
            requests_from_request_file_func (Callable): Function to parse requests from file

        Side Effects:
            - Updates batch submission progress bar
            - Updates tracker with submitted batch status
        """
        metadata = {"request_file_name": request_file}
        requests = await requests_from_request_file_func(request_file)
        batch_object = await self.submit_batch(requests, metadata)
        self.tracker.mark_as_submitted(request_file, batch_object)
        self.batch_submit_pbar.update(1)

    async def track_already_submitted_batches(self):
        """
        Tracks previously submitted batches from the submitted batch objects file.

        Side Effects:
            - Updates tracker with previously submitted batch statuses
        """
        if os.path.exists(self.submitted_batch_objects_file):
            with open(self.submitted_batch_objects_file, "r") as f:
                for line in f:
                    batch_object = Batch.model_validate(json.loads(line))
                    request_file_name = batch_object.metadata["request_file_name"]
                    logger.debug(
                        f"Already submitted batch {batch_object.id} for request file {request_file_name}. "
                        f"Getting batch object to update tracker."
                    )
                    batch_object = await self.retrieve_batch(batch_object.id)
                    if request_file_name in self.tracker.unsubmitted_request_files:
                        self.tracker.mark_as_submitted(request_file_name, batch_object)

        self.tracker.n_total_batches += len(self.tracker.unsubmitted_request_files)
        if self.tracker.n_submitted_batch_ids > 0:
            logger.info(
                f"{self.tracker.n_submitted_batch_ids:,} out of {self.tracker.n_total_batches - self.tracker.n_downloaded_batch_ids:,} remaining batches are already submitted."
            )

    async def track_already_downloaded_batches(self):
        """
        Tracks previously downloaded batches from the downloaded batch objects files.

        Side Effects:
            - Updates tracker with previously downloaded batch statuses
        """
        downloaded_batch_object_files = set(
            glob.glob(f"{self.working_dir}/batch_objects_downloaded_*.jsonl")
        )
        for downloaded_batch_object_file in downloaded_batch_object_files:
            with open(downloaded_batch_object_file, "r") as f:
                for line in f:
                    batch_object = Batch.model_validate(json.loads(line))
                    request_file = batch_object.metadata["request_file_name"]
                    response_file = request_file_to_response_file(request_file, self.working_dir)
                    assert request_file in self.tracker.unsubmitted_request_files
                    assert os.path.exists(response_file)
                    self.tracker.mark_as_submitted(request_file, batch_object)
                    self.tracker.mark_as_finished(batch_object)
                    self.tracker.mark_as_downloaded(batch_object)

        if self.tracker.n_downloaded_batch_ids > 0:
            logger.info(
                f"{self.tracker.n_downloaded_batch_ids:,} out of {self.tracker.n_total_batches:,} batches already downloaded."
            )

    async def submit_batches_from_request_files(
        self,
        request_files: set[str],
        requests_from_request_file_func: Callable = requests_from_api_specific_request_file,
    ):
        """
        Manages the submission of multiple request files as batches.

        Args:
            request_files (set[str]): Set of paths to request files to process
            requests_from_request_file_func (Callable): Function to parse requests from files

        Side Effects:
            - Updates tracker with batch statuses
            - Creates and updates batch submission progress bar
        """
        self.tracker.unsubmitted_request_files = request_files
        await self.track_already_downloaded_batches()
        await self.track_already_submitted_batches()
        # exit early
        if self.tracker.n_unsubmitted_request_files == 0:
            return

        # submit remaining batches
        self.batch_submit_pbar = tqdm(
            total=self.tracker.n_total_batches,
            desc="Submitting batches",
            unit="batch",
            initial=self.tracker.n_submitted_batch_ids,
        )
        tasks = [
            self.submit_batch_from_request_file(f, requests_from_request_file_func)
            for f in self.tracker.unsubmitted_request_files
        ]
        await asyncio.gather(*tasks)
        self.batch_submit_pbar.close()
        assert self.tracker.unsubmitted_request_files == set()
        logger.debug(
            f"All batch objects submitted and written to {self.submitted_batch_objects_file}"
        )

    async def check_batch_status(self, batch_id: str) -> Batch | None:
        """
        Checks the current status of a batch job.

        Args:
            batch_id (str): The ID of the batch to check

        Returns:
            Batch | None: The batch object if completed (including failures), None if in progress

        Side Effects:
            - Updates tracker with current batch status
            - Updates request completion counts
        """
        async with self.semaphore:
            batch = await self.client.batches.retrieve(batch_id)

            n_completed_requests = batch.request_counts.completed
            n_failed_requests = batch.request_counts.failed
            n_total_requests = batch.request_counts.total

            self.tracker.n_finished_requests += n_completed_requests + n_failed_requests

            logger.debug(
                f"Batch {batch.id} status: {batch.status} requests: "
                f"{n_completed_requests}/{n_failed_requests}/{n_total_requests} "
                "completed/failed/total"
            )

            finished_statuses = ["completed", "failed", "expired", "cancelled"]
            in_progress_statuses = ["validating", "finalizing", "cancelling", "in_progress"]
            batch_returned = batch.status in finished_statuses
            if batch.status not in in_progress_statuses + finished_statuses:
                logger.warning(f"Unknown batch status: {batch.status}")

            if batch_returned:
                logger.debug(f"Batch {batch.id} returned with status: {batch.status}")
                self.tracker.submitted_batch_ids.remove(batch.id)
                self.tracker.finished_batch_ids.add(batch.id)
                return batch

    async def poll_and_process_batches(
        self,
        response_file_from_responses_func: Callable = api_specific_response_file_from_responses,
    ) -> None:
        """Monitors and processes batches until all are completed.

        Continuously polls the status of submitted batches and downloads their results
        when complete. Handles successful completions, failures, expirations, and
        cancellations. Progress is tracked via a progress bar showing completed requests.

        Returns:
            None

        Raises:
            RuntimeError: If none of the submitted batches complete successfully.

        Side Effects:
            - Updates the batch tracker state
            - Creates response files for completed batches
            - Creates and updates requests progress bar
        """
        # progress bar for finished requests
        self.request_pbar = tqdm(
            total=self.tracker.n_total_requests,
            desc="Finished requests in batches",
            unit="request",
            initial=self.tracker.n_finished_requests + self.tracker.n_downloaded_requests,
        )

        # loop until all batches have been returned
        all_response_files = []
        while len(self.tracker.submitted_batch_ids) > 0:
            # check batch status also updates the tracker
            status_tasks = [
                self.check_batch_status(batch_id) for batch_id in self.tracker.submitted_batch_ids
            ]
            batches_to_download = await asyncio.gather(*status_tasks)
            batches_to_download = filter(None, batches_to_download)

            # update progress bar
            self.request_pbar.n = (
                self.tracker.n_finished_requests + self.tracker.n_downloaded_requests
            )
            self.request_pbar.refresh()

            download_tasks = [
                self.download_batch_to_response_file(batch, response_file_from_responses_func)
                for batch in batches_to_download
            ]
            # Failed downloads return None and print any errors that occurred
            all_response_files.extend(await asyncio.gather(*download_tasks))
            if (
                self.tracker.n_finished_requests + self.tracker.n_downloaded_requests
                < self.tracker.n_total_requests
            ):
                logger.debug(
                    f"Batches returned: {len(self.tracker.finished_batch_ids) + len(self.tracker.downloaded_batch_ids)}/{len(self.tracker.submitted_batch_ids) + len(self.tracker.finished_batch_ids) + len(self.tracker.downloaded_batch_ids)} "
                    f"Requests completed: {self.tracker.n_finished_requests + self.tracker.n_downloaded_requests}/{self.tracker.n_total_requests}"
                )
                logger.debug(f"Sleeping for {self.check_interval} seconds...")
                await asyncio.sleep(self.check_interval)

        self.request_pbar.close()
        response_files = filter(None, all_response_files)
        if len(self.tracker.downloaded_batch_ids) == 0 or not response_files:
            raise RuntimeError(
                "None of the submitted batches completed successfully. "
                "Please check the logs above and https://platform.openai.com/batches for errors."
            )

    async def delete_file(self, file_id: str, semaphore: asyncio.Semaphore):
        """
        Deletes a file from OpenAI's storage.

        Args:
            file_id (str): The ID of the file to delete
            semaphore (asyncio.Semaphore): Semaphore to limit concurrent operations
        """
        async with semaphore:
            delete_response = await self.client.files.delete(file_id)
            if delete_response.deleted:
                logger.debug(f"Deleted file {file_id}")
            else:
                logger.warning(f"Failed to delete file {file_id}")

    async def download_batch(self, batch: Batch) -> str | None:
        file_content = None
        async with self.semaphore:
            # Completed batches have an output file
            if batch.status == "completed" and batch.output_file_id:
                file_content = await self.client.files.content(batch.output_file_id)
                logger.debug(f"Batch {batch.id} completed and downloaded")

            # Failed batches with an error file
            elif batch.status == "failed" and batch.error_file_id:
                file_content = await self.client.files.content(batch.error_file_id)
                logger.warning(f"Batch {batch.id} failed\n. Errors will be parsed below.")
                if self.delete_failed_batch_files:
                    await self.delete_file(batch.input_file_id, self.semaphore)
                    await self.delete_file(batch.error_file_id, self.semaphore)

            # Failed batches without an error file
            elif batch.status == "failed" and not batch.error_file_id:
                errors = "\n".join([str(error) for error in batch.errors.data])
                logger.error(
                    f"Batch {batch.id} failed and likely failed validation. "
                    f"Batch errors: {errors}. "
                    f"Check https://platform.openai.com/batches/{batch.id} for more details."
                )
                if self.delete_failed_batch_files:
                    await self.delete_file(batch.input_file_id, self.semaphore)

            # Cancelled or expired batches
            elif batch.status == "cancelled" or batch.status == "expired":
                logger.warning(f"Batch {batch.id} was cancelled or expired")
                if self.delete_failed_batch_files:
                    await self.delete_file(batch.input_file_id, self.semaphore)

        return file_content

    async def download_batch_to_response_file(
        self,
        batch: Batch,
        response_file_from_responses_func: Callable = api_specific_response_file_from_responses,
    ) -> str | None:
        """
        Downloads and processes the results of a completed batch.

        Handles successful completions, failures, and error cases. Converts API-specific
        responses to generic responses and calculates costs.

        Args:
            batch (Batch): The completed batch object to process

        Returns:
            str | None: Path to the response file if successful, None if batch failed

        Side Effects:
            - Creates response file with processed results
            - Updates batch tracking state
            - Appends batch object to downloaded batch objects file
            - Optionally deletes batch files from OpenAI
        """
        file_content = await self.download_batch(batch)

        if file_content is None:
            return None

        request_file = batch.metadata["request_file_name"]
        response_file = request_file_to_response_file(request_file, self.working_dir)
        await response_file_from_responses_func(file_content, batch, response_file)

        logger.debug(f"Batch {batch.id} written to {response_file}")

        # Simplified file writing
        with open(self.downloaded_batch_objects_file, "a") as f:
            json.dump(batch.model_dump(), f, default=str)
            f.write("\n")
            f.flush()

        logger.debug(f"Batch {batch.id} written to {self.downloaded_batch_objects_file}")

        if self.delete_successful_batch_files:
            await self.delete_file(batch.input_file_id, self.semaphore)
            await self.delete_file(batch.output_file_id, self.semaphore)

        self.tracker.mark_as_downloaded(batch)

        return response_file
