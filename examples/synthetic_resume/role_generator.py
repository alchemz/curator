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

    def get_role_sections(self, role: str, level: str) -> List[str]:
        """Get recommended sections for a specific role"""
        messages = [
            {
                "role": "system",
                "content": """You are an expert in tech industry resumes. Determine which sections should be included 
                in a resume based on the role and level."""
            },
            {
                "role": "user",
                "content": f"""For a {level} {role}, what sections should be included in their resume?
                Consider both standard sections (summary, experience, education, skills) and role-specific sections.
                
                Available sections include:
                - publications (for research/academic roles)
                - certifications (for specialized technical roles)
                - awards (for distinguished achievements)
                - languages (for international/multilingual roles)
                - research_projects (for R&D roles)
                - portfolio (for creative/frontend roles)
                - open_source (for software engineering roles)
                - system_architecture (for senior/architect roles)
                - infrastructure (for DevOps/SRE roles)
                - security (for security-focused roles)
                - app_store (for mobile developers)
                - volunteer (for community involvement)

                Return a JSON array of section names that are relevant for this role.
                Example: ["summary", "experience", "education", "skills", "publications"]"""
            }
        ]

        try:
            dataset = [{"messages": messages}]
            response = self(dataset)
            
            if response and len(response) > 0:
                content = response[0]
                if isinstance(content, dict) and "choices" in content:
                    content = content["choices"][0]["message"]["content"]
                
                # Clean up and parse JSON
                if isinstance(content, str):
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content.replace("```json", "", 1)
                    if content.endswith("```"):
                        content = content[:-3]
                    sections = json.loads(content.strip())
                    return sections

            return self._get_default_sections()
            
        except Exception as e:
            logger.error(f"Error getting role sections: {str(e)}")
            return self._get_default_sections()

    def _get_default_sections(self) -> List[str]:
        """Return default sections if section generation fails"""
        return ["summary", "experience", "education", "skills"]

    def get_variations(self, num_resumes: int = 1) -> List[Dict]:
        """Generate varied tech role configurations with recommended sections"""
        try:
            # Make LLM call with num_resumes in input
            dataset = [{"num_resumes": num_resumes}]
            logger.info(f"Requesting {num_resumes} role variations from LLM...")
            response = self(dataset)
            
            logger.info(f"Raw LLM response: {response}")
            
            # Handle Dataset object
            if hasattr(response, 'features') and hasattr(response, 'num_rows'):
                variations = []
                for i in range(response.num_rows):
                    variation = {
                        'role': response[i]['role'],
                        'level': response[i]['level'],
                        'focus': response[i]['focus'],
                        'tech_stack': response[i]['tech_stack'],
                        'years': response[i]['years']
                    }
                    # Add recommended sections
                    sections = self.get_role_sections(variation['role'], variation['level'])
                    variation['recommended_sections'] = sections
                    variations.append(variation)
                return variations
            
            # Handle other response formats (fallback)
            if response and len(response) > 0:
                content = response[0]
                logger.info(f"Content from response: {content}")
                
                if isinstance(content, dict):
                    if "choices" in content:
                        content = content["choices"][0]["message"]["content"]
                    elif all(key in content for key in ["role", "level", "focus", "tech_stack", "years"]):
                        # Single variation returned as dict
                        variations = [content]
                        for var in variations:
                            sections = self.get_role_sections(var['role'], var['level'])
                            var['recommended_sections'] = sections
                        return variations
                
                # ... rest of the existing parsing logic ...
            
            logger.error("Failed to generate role variations - empty or invalid response")
            return self._get_fallback_variations(num_resumes)
            
        except Exception as e:
            logger.error(f"Error generating role variations: {str(e)}")
            logger.error(f"Full error details:", exc_info=True)
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
        logger.info("Using fallback variations")  # Debug log
        fallback_variations = [
            {
                "role": "Software Engineer",
                "level": "Mid-level",
                "focus": "Full-stack Development",
                "tech_stack": "Python, JavaScript, React, AWS",
                "years": "4-6",
                "recommended_sections": ["summary", "experience", "education", "skills", "open_source"]
            },
            {
                "role": "Data Scientist",
                "level": "Senior",
                "focus": "Machine Learning",
                "tech_stack": "Python, PyTorch, SQL, AWS",
                "years": "7-10",
                "recommended_sections": ["summary", "experience", "education", "skills", "publications", "research_projects"]
            },
            {
                "role": "DevOps Engineer",
                "level": "Mid-level",
                "focus": "Infrastructure Automation",
                "tech_stack": "Kubernetes, Terraform, AWS, Python",
                "years": "4-6",
                "recommended_sections": ["summary", "experience", "education", "skills", "infrastructure"]
            }
        ]
        
        # Return requested number of variations (with repeats if necessary)
        return fallback_variations[:num_resumes] if num_resumes <= len(fallback_variations) else \
               fallback_variations * (num_resumes // len(fallback_variations) + 1) 