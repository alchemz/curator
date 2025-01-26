import logging
import json
import os
import re
import argparse
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv
from bespokelabs import curator
from prompts import RESUME_SYSTEM_PROMPT, generate_user_prompt

from datamodels import Resume
from name_generator import NameGenerator
from role_generator import RoleGenerator
from pdf_generator import create_pdf

# Load environment variables from .env file
load_dotenv()

# Check for DeepSeek API key
if not os.getenv("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set. Please set it before running the script.")

logger = logging.getLogger(__name__)

class ResumeGenerator(curator.LLM):
    """A resume generator that creates realistic tech industry resumes"""
    
    return_completions_object = True

    def __init__(self):
        super().__init__(
            model_name="deepseek-reasoner",
            backend_params={
                "max_requests_per_minute": 10000,
                "max_tokens_per_minute": 10000000,
                "request_timeout": 30 * 60,
            },
            generation_params={
                "temperature": 0.7,
                "max_tokens": 2048,
            }
        )

    def __call__(self, dataset: List[Dict]) -> List[Dict]:
        """Generate resume data from role variation"""
        try:
            # Generate prompt
            messages = self.prompt(dataset[0])
            
            # Make LLM call using self directly since we inherit from curator.LLM
            response = super().__call__([{"messages": messages}])
            logger.info(f"LLM response received: {response}")
            
            # Parse response
            result = self.parse_response(response)
            if not result:
                logger.error("Failed to parse LLM response")
                return []
                
            return result
            
        except Exception as e:
            logger.error(f"Error in resume generation: {str(e)}")
            return []

    def prompt(self, input: dict) -> List[dict]:
        """Generate the prompt as a list of messages"""
        role_variation = input.get('role_variation', {
            'role': 'Software Engineer',
            'level': 'Mid-level',
            'focus': 'Full-stack development',
            'tech_stack': 'Python, JavaScript, and cloud technologies',
            'years': '4-6'
        })
        
        # Get recommended sections
        sections = role_variation.get('recommended_sections', ["summary", "experience", "education", "skills"])
        requires_publications = role_variation.get('requires_publications', False)
        
        # Build dynamic schema based on sections
        schema = {
            "personal_info": {
                "name": "string",
                "email": "string",
                "phone": "string",
                "location": "string",
                "linkedin": "string",
                "github": "string (optional)",
                "portfolio": "string (optional)"
            }
        }
        
        # Add required sections
        for section in sections:
            if section == "summary":
                schema["summary"] = "string"
            elif section == "experience":
                schema["experience"] = [{
                    "title": "string",
                    "company": "string",
                    "location": "string",
                    "start_date": "string",
                    "end_date": "string",
                    "responsibilities": ["string"],
                    "technologies": ["string"]
                }]
            elif section == "education":
                schema["education"] = [{
                    "degree": "string",
                    "field": "string",
                    "university": "string",
                    "location": "string",
                    "year": "number",
                    "gpa": "number",
                    "relevant_coursework": ["string"]
                }]
            elif section == "skills":
                schema["skills"] = ["string"]
            elif section == "publications" or requires_publications:
                schema["publications"] = [{
                    "title": "string",
                    "authors": ["string"],
                    "journal": "string",
                    "year": "number",
                    "link": "string (optional)",
                    "impact_factor": "number (optional)",
                    "citations": "number (optional)"
                }]
            # ... other sections ...

        # Build the system prompt with emphasis on publications for ML/AI roles
        system_prompt = f"""You are a professional resume writer. Create a realistic and detailed tech industry resume.
        Your response must be a valid JSON object that follows this exact structure:
        
        {json.dumps(schema, indent=2)}
        
        Ensure:
        1. All dates are in YYYY-MM format
        2. GPA is a number between 0.0 and 4.0
        3. Year is a four-digit number
        4. All arrays must contain at least one item
        """
        
        if requires_publications:
            system_prompt += """
        5. For this ML/AI role, you MUST include at least 2 relevant publications
        6. Publications should be realistic and related to the role's focus area
        7. Include both conference and journal publications if possible
        """
        
        system_prompt += "\nReturn only the JSON object, no additional text."

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": generate_user_prompt(role_variation)}
        ]

    def parse_response(self, response: Dict) -> List[Dict]:
        """Parse LLM response into resume data"""
        try:
            # Handle Dataset response
            if hasattr(response, 'to_dict'):
                response_dict = response[0]
                content = response_dict['choices'][0]['message']['content']
            else:
                content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            logger.info(f"Raw content before cleaning: {content}")
            
            # Clean the content
            content = content.replace('```json', '').replace('```', '').strip()
            content = content.encode('ascii', 'ignore').decode('ascii')
            
            logger.info(f"Cleaned content: {content}")
            
            try:
                # Parse JSON
                resume_data = json.loads(content)
                logger.info(f"Parsed JSON: {json.dumps(resume_data, indent=2)}")
                
                # Ensure skills is a simple list of strings
                if 'skills' in resume_data:
                    if isinstance(resume_data['skills'], dict):
                        # If it's a dict with items, extract the items
                        resume_data['skills'] = resume_data['skills'].get('items', [])
                    elif isinstance(resume_data['skills'], list):
                        # If it's a list of dicts, extract just the skill strings
                        if resume_data['skills'] and isinstance(resume_data['skills'][0], dict):
                            all_skills = []
                            for category in resume_data['skills']:
                                if isinstance(category, dict):
                                    all_skills.extend(category.get('items', []))
                            resume_data['skills'] = all_skills
                else:
                    resume_data['skills'] = []
                
                # Ensure required top-level fields exist
                required_fields = ['personal_info', 'summary', 'experience', 'education', 'skills']
                for field in required_fields:
                    if field not in resume_data:
                        logger.error(f"Missing required field: {field}")
                        resume_data[field] = {} if field == 'personal_info' else []
                
                # Validate against model
                resume = Resume(**resume_data)
                result = resume.dict()
                logger.info(f"Validated resume data: {json.dumps(result, indent=2)}")
                
                return [result]
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                logger.debug(f"Content that failed to parse: {content}")
                return []
                
        except Exception as e:
            logger.error(f"Error parsing resume data: {str(e)}")
            logger.error(f"Response type: {type(response)}")
            logger.error(f"Response content: {response}")
            return []

def main():
    """Generate synthetic resumes using curator and DeepSeek API"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate synthetic resumes using DeepSeek API')
    parser.add_argument('-n', '--num_resumes', type=int, default=1,
                      help='Number of resumes to generate (default: 1)')
    args = parser.parse_args()
    
    print(f"Initializing ResumeGenerator to create {args.num_resumes} resumes...")
    
    try:
        # Initialize generator
        resume_generator = ResumeGenerator()
        print("Debug: ResumeGenerator instance created successfully")
        
        # Create base output directory
        base_output_dir = "generated_resumes"
        if not os.path.exists(base_output_dir):
            os.makedirs(base_output_dir)
            print(f"Created base output directory: {base_output_dir}")

        # Create timestamped subfolder for this run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(base_output_dir, f"attempt_{timestamp}")
        os.makedirs(output_dir)
        print(f"Created output directory for this run: {output_dir}")

        # Initialize generators
        role_generator = RoleGenerator()
        name_generator = NameGenerator()
        
        # Get role variations based on requested number
        variations = role_generator.get_variations(args.num_resumes)
        num_resumes = len(variations)
        successful = 0
        
        for i, variation in enumerate(variations):
            print(f"\nGenerating resume {i+1}/{num_resumes} for {variation['level']} {variation['role']}...")
            try:
                # Generate a unique name for this resume
                unique_name = name_generator.get_unique_name()
                variation['name'] = unique_name
                
                # Generate a resume with this variation
                dataset = resume_generator([{'role_variation': variation}])
                
                if not dataset or len(dataset) == 0:
                    print(f"No data generated for resume {i+1}")
                    continue
                    
                # Extract the resume data
                resume_data = dataset[0]
                
                # Ensure the generated resume uses the unique name
                resume_data["personal_info"]["name"] = unique_name
                
                # Create a filesystem-safe version of the name
                safe_name = unique_name.lower().replace(' ', '_')
                safe_name = re.sub(r'[^a-z0-9_]', '', safe_name)
                role_name = variation['role'].lower().replace(' ', '_')
                
                # Save as JSON
                json_path = os.path.join(output_dir, f"resume_{safe_name}_{role_name}.json")
                print(f"Saving JSON to: {json_path}")
                with open(json_path, 'w') as f:
                    json.dump(resume_data, f, indent=2)
                
                # Generate PDF
                pdf_path = os.path.join(output_dir, f"resume_{safe_name}_{role_name}.pdf")
                print(f"Generating PDF: {pdf_path}")
                if create_pdf(resume_data, pdf_path):
                    print(f"Successfully generated resume {i+1}")
                    print(f"Files created:\n- {json_path}\n- {pdf_path}")
                    successful += 1
                else:
                    print(f"Failed to create PDF for resume {i+1}")
                    
            except Exception as e:
                print(f"Error generating resume {i+1}: {str(e)}")
                continue
        
        # Print summary
        print(f"\nGeneration complete!")
        print(f"Successfully generated {successful} out of {num_resumes} resumes")
        if successful > 0:
            print(f"Files are saved in: {output_dir}")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main() 