import logging
import json
from typing import List, Dict
from bespokelabs import curator

logger = logging.getLogger(__name__)

class RoleGenerator(curator.LLM):
    """Generates varied tech industry roles using LLM"""
    
    def __init__(self):
        super().__init__(
            model_name="deepseek-reasoner",
            backend_params={
                "max_requests_per_minute": 10000,
                "max_tokens_per_minute": 10000000,
                "request_timeout": 30 * 60,
            },
            generation_params={
                "temperature": 0.8,
                "max_tokens": 1000,
            }
        )
        self.role_cache = {}

    def prompt(self, input: dict) -> List[dict]:
        """Generate the prompt messages for LLM"""
        num_resumes = input.get('num_resumes', 1)
        
        return [
            {
                "role": "system",
                "content": """You are an expert in tech industry roles and career paths. Generate realistic tech role variations 
                that reflect current industry standards and market demands."""
            },
            {
                "role": "user",
                "content": f"""Generate {num_resumes} different tech role variations. 
                Each role should include:
                - role: The job title
                - level: Experience level (Junior, Mid-level, Senior, Lead, Principal)
                - focus: Main focus area or specialization
                - tech_stack: Relevant and modern technology stack
                - years: Years of experience range appropriate for the level

                Return the response as a JSON array of objects. Example format:
                [
                    {{
                        "role": "Software Engineer",
                        "level": "Senior",
                        "focus": "Backend Development",
                        "tech_stack": "Go, PostgreSQL, Kubernetes, AWS",
                        "years": "7-10"
                    }}
                ]

                Ensure:
                1. Tech stacks are modern and realistic for the role
                2. Years of experience match the level
                3. Focus areas are specific to the role
                4. Include varied roles (not just Software Engineer)
                5. Include emerging tech roles and stacks where appropriate

                Only return the JSON array, no other text."""
            }
        ]

    def get_variations(self, num_resumes: int = 1) -> List[Dict]:
        """Generate varied tech role configurations"""
        try:
            # Make LLM call with num_resumes in input
            dataset = [{"num_resumes": num_resumes}]
            response = self(dataset)
            
            if response and len(response) > 0:
                content = response[0]
                if isinstance(content, dict) and "choices" in content:
                    content = content["choices"][0]["message"]["content"]
                
                # Clean up content
                if isinstance(content, str):
                    # Remove markdown code blocks if present
                    if content.startswith("```json"):
                        content = content.replace("```json", "", 1)
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    variations = json.loads(content)
                    
                    # Validate structure
                    required_keys = {"role", "level", "focus", "tech_stack", "years"}
                    for var in variations:
                        if not all(key in var for key in required_keys):
                            raise ValueError(f"Missing required keys in variation: {var}")
                    
                    return variations

            logger.error("Failed to generate role variations")
            return self._get_fallback_variations(num_resumes)
            
        except Exception as e:
            logger.error(f"Error generating role variations: {str(e)}")
            return self._get_fallback_variations(num_resumes)

    def parse(self, input: dict, response: dict) -> List[Dict]:
        """Parse the LLM response"""
        try:
            # Handle different response formats
            if isinstance(response, list) and len(response) > 0:
                content = response[0]
            else:
                content = response

            # Extract content from different possible formats
            if isinstance(content, dict):
                if "choices" in content:
                    content = content["choices"][0]["message"]["content"]
                elif "content" in content:
                    content = content["content"]
            elif isinstance(content, str):
                content = content
            else:
                logger.error(f"Unexpected response format: {type(content)}")
                return self._get_fallback_variations(input.get('num_resumes', 1))

            # Clean up content
            if isinstance(content, str):
                if content.startswith("```json"):
                    content = content.replace("```json", "", 1)
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                variations = json.loads(content)
                
                # Validate structure
                required_keys = {"role", "level", "focus", "tech_stack", "years"}
                for var in variations:
                    if not all(key in var for key in required_keys):
                        raise ValueError(f"Missing required keys in variation: {var}")
                
                return variations
            
            logger.error("Failed to parse content")
            return self._get_fallback_variations(input.get('num_resumes', 1))
            
        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            logger.debug(f"Raw response: {response}")
            return self._get_fallback_variations(input.get('num_resumes', 1))

    def _get_fallback_variations(self, num_resumes: int) -> List[Dict]:
        """Fallback method in case LLM generation fails"""
        fallback_variations = [
            {
                "role": "Software Engineer",
                "level": "Mid-level",
                "focus": "Full-stack Development",
                "tech_stack": "Python, JavaScript, React, AWS",
                "years": "4-6"
            },
            {
                "role": "Data Scientist",
                "level": "Senior",
                "focus": "Machine Learning",
                "tech_stack": "Python, PyTorch, SQL, AWS",
                "years": "7-10"
            },
            {
                "role": "DevOps Engineer",
                "level": "Mid-level",
                "focus": "Infrastructure Automation",
                "tech_stack": "Kubernetes, Terraform, AWS, Python",
                "years": "4-6"
            }
        ]
        
        # Return requested number of variations (with repeats if necessary)
        return fallback_variations[:num_resumes] if num_resumes <= len(fallback_variations) else \
               fallback_variations * (num_resumes // len(fallback_variations) + 1) 