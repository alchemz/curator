"""Prompts for resume generation."""

RESUME_SYSTEM_PROMPT = """You are a professional resume writer. Create a realistic and detailed tech industry resume. 
Your response must be a valid JSON object with this exact structure, with no additional text or explanation:
{
    "personal_info": {
        "name": "string",
        "email": "string",
        "phone": "string",
        "location": "string",
        "linkedin": "string",
        "github": "string (optional)",
        "portfolio": "string (optional)"
    },
    "summary": "string",
    "experience": [{
        "title": "string",
        "company": "string",
        "location": "string",
        "start_date": "string",
        "end_date": "string",
        "responsibilities": ["string"],
        "technologies": ["string"]
    }],
    "education": [{
        "degree": "string",
        "field": "string",
        "university": "string",
        "location": "string",
        "year": number,
        "gpa": number,
        "relevant_coursework": ["string"]
    }],
    "skills": ["string"],
    "certifications": ["string"]
}"""

def generate_user_prompt(role_variation: dict) -> str:
    """Generate a user prompt for resume creation based on role variation"""
    name = role_variation.get('name', 'John Smith')  # Use provided name or default
    role = role_variation['role']
    level = role_variation['level']
    focus = role_variation['focus']
    tech_stack = role_variation['tech_stack']
    years = role_variation['years']
    
    return f"""Please create a realistic resume for {name}, a {level} {role} with {years} years of experience. 
Their focus is on {focus} using {tech_stack}. 
The resume should include:
1. Relevant work experience with specific achievements and metrics
2. Education background appropriate for their role and level
3. Technical skills aligned with their focus area
4. Professional certifications if applicable

Please format the response as a JSON object that matches the schema defined in the system prompt.""" 