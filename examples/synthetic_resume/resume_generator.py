import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from bespokelabs import curator
from fpdf import FPDF
import json
import os
import argparse
import random
from dotenv import load_dotenv
from prompts import RESUME_SYSTEM_PROMPT, generate_user_prompt
from fpdf.enums import XPos, YPos

# Load environment variables from .env file
load_dotenv()

# Check for DeepSeek API key
if not os.getenv("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set. Please set it before running the script.")

logger = logging.getLogger(__name__)

# Move Pydantic models to models.py
class PersonalInfo(BaseModel):
    """Personal information section of a resume"""
    name: str = Field(description="Full name of the person")
    email: str = Field(description="Professional email address")
    phone: str = Field(description="Phone number in standard format")
    location: str = Field(description="City and state")
    linkedin: str = Field(description="LinkedIn profile URL")
    github: Optional[str] = Field(description="GitHub profile URL")
    portfolio: Optional[str] = Field(description="Personal portfolio website")

class Experience(BaseModel):
    """Work experience entry"""
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str = Field(description="Job location (city, state)")
    start_date: str = Field(description="Start date of employment")
    end_date: str = Field(description="End date of employment or 'Present'")
    responsibilities: List[str] = Field(description="List of job responsibilities and achievements")
    technologies: List[str] = Field(description="Technologies and tools used")

class Education(BaseModel):
    """Education entry"""
    degree: str = Field(description="Degree type")
    field: str = Field(description="Field of study")
    university: str = Field(description="University name")
    location: str = Field(description="University location")
    year: int = Field(description="Graduation year")
    gpa: float = Field(description="GPA on a 4.0 scale")
    relevant_coursework: List[str] = Field(description="List of relevant courses")

class Resume(BaseModel):
    """Complete resume structure"""
    personal_info: PersonalInfo = Field(description="Personal and contact information")
    summary: str = Field(description="Professional summary")
    experience: List[Experience] = Field(description="Work experience entries")
    education: List[Education] = Field(description="Education entries")
    skills: List[str] = Field(description="Technical and professional skills")
    certifications: Optional[List[str]] = Field(description="Professional certifications")

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

    def __call__(self, dataset=None):
        """Override to handle empty input case"""
        if dataset is None:
            dataset = [{}]  # Pass empty dict as input
        return super().__call__(dataset)

    def prompt(self, input: dict) -> List[dict]:
        """Generate the prompt as a list of messages"""
        # Get role variation from input or use default
        role_variation = input.get('role_variation', {
            'role': 'Software Engineer',
            'level': 'Mid-level',
            'focus': 'Full-stack development',
            'tech_stack': 'Python, JavaScript, and cloud technologies',
            'years': '4-6'
        })

        return [
            {"role": "system", "content": RESUME_SYSTEM_PROMPT},
            {"role": "user", "content": generate_user_prompt(role_variation)}
        ]

    def parse(self, input: dict, response: dict) -> dict:
        """Parse the LLM response to extract the resume data"""
        try:
            # Extract content from the completions object
            content = response["choices"][0]["message"]["content"]
            
            # Remove markdown code block if present
            if content.startswith("```json"):
                content = content.replace("```json", "", 1)
            if content.endswith("```"):
                content = content[:-3]
            
            # Clean up any remaining whitespace
            content = content.strip()
            
            # Parse the content into Resume format
            parsed = json.loads(content)
            
            # Validate against our Pydantic model and convert to dict
            resume = Resume(**parsed)
            return resume.model_dump()  # Updated from dict() to model_dump()
        except Exception as e:
            print(f"Debug: Error parsing response: {str(e)}")
            print(f"Debug: Raw response: {response}")
            raise

def create_pdf(resume_data: dict, output_path: str) -> bool:
    """Create a PDF version of the resume"""
    class PDF(FPDF):
        def __init__(self):
            super().__init__()
            # Choose a random font family for this resume
            self.font_family = random.choice(['helvetica', 'times', 'courier'])
            self.set_font(self.font_family)
            # Set margins
            self.set_margins(15, 15, 15)
            self.set_auto_page_break(auto=True, margin=15)
            # Set bullet point based on font
            self.bullet = '*' if self.font_family == 'courier' else '-'

        def header(self):
            """Custom header with consistent font family"""
            self.set_font(self.font_family)

        def wrapped_cell(self, w, h, txt, border=0, align='L', new_x=XPos.LMARGIN, new_y=YPos.NEXT):
            """Custom cell with text wrapping"""
            # Replace bullet points with font-appropriate version
            txt = txt.replace('•', self.bullet)
            
            # Get the current position
            x = self.get_x()
            y = self.get_y()
            
            # Calculate available width
            available_width = w if w > 0 else self.epw
            
            # For Courier font, reduce the text length threshold
            if self.font_family == 'courier':
                available_width = available_width * 0.85  # Reduce width for better wrapping
            
            # Split the text into lines that fit the width
            lines = []
            words = txt.split()
            current_line = []
            
            for word in words:
                current_line.append(word)
                test_line = ' '.join(current_line)
                if self.get_string_width(test_line) > available_width:
                    if len(current_line) > 1:
                        current_line.pop()
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(test_line)
                        current_line = []
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Print each line
            for i, line in enumerate(lines):
                self.set_xy(x, y + i * h)
                self.cell(w, h, line, border, 0, align)
            
            # Move to the next position
            if new_x == XPos.LMARGIN:
                self.set_x(self.l_margin)
            elif new_x == XPos.RIGHT:
                self.set_x(self.r_margin)
            
            if new_y == YPos.NEXT:
                self.set_y(y + len(lines) * h)
            
            return len(lines)  # Return number of lines used

        def format_skills(self, skills):
            """Format skills into columns for better space usage"""
            # For Courier font, use fewer columns due to wider characters
            num_columns = 2 if self.font_family == 'courier' else 3
            
            # Split skills into roughly equal columns
            skills_per_column = (len(skills) + num_columns - 1) // num_columns
            columns = []
            for i in range(0, len(skills), skills_per_column):
                columns.append(skills[i:i + skills_per_column])
            
            # Calculate column width with more spacing
            spacing = 15  # Increased spacing between columns
            col_width = (self.epw - (num_columns - 1) * spacing) / num_columns
            
            # Current position
            x_start = self.get_x()
            y_start = self.get_y()
            max_y = y_start
            
            # Print each column
            for i, column in enumerate(columns):
                current_x = x_start + i * (col_width + spacing)
                current_y = y_start
                
                for skill in column:
                    self.set_xy(current_x, current_y)
                    # Pre-calculate wrapped lines to determine height
                    lines = []
                    words = skill.split()
                    current_line = []
                    
                    for word in words:
                        current_line.append(word)
                        test_line = ' '.join(current_line)
                        if self.get_string_width(f"{self.bullet} {test_line}") > col_width:
                            if len(current_line) > 1:
                                current_line.pop()
                                lines.append(' '.join(current_line))
                                current_line = [word]
                            else:
                                lines.append(test_line)
                                current_line = []
                    
                    if current_line:
                        lines.append(' '.join(current_line))
                    
                    # Print each line of the skill
                    for line in lines:
                        self.set_xy(current_x, current_y)
                        if line == lines[0]:  # First line includes bullet
                            self.cell(col_width, 5, f"{self.bullet} {line}", 0, 1)
                        else:  # Continuation lines are indented
                            self.cell(col_width, 5, f"    {line}", 0, 1)
                        current_y += 5
                    
                    if not lines:  # If no wrapping occurred
                        self.cell(col_width, 5, f"{self.bullet} {skill}", 0, 1)
                        current_y += 5
                    
                    # Add some spacing between skills
                    current_y += 2
                    
                    if current_y > max_y:
                        max_y = current_y
            
            # Move to position after all columns
            self.set_xy(x_start, max_y)

    pdf = PDF()
    pdf.add_page()
    
    # Name
    pdf.set_font(pdf.font_family, 'B', 16)
    pdf.cell(0, 10, resume_data["personal_info"]["name"], new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    
    # Contact info on one line with separators
    pdf.set_font(pdf.font_family, '', 10)
    contact_info = []
    
    # Phone and email
    contact_info.append(resume_data["personal_info"]["phone"])
    contact_info.append(resume_data["personal_info"]["email"])
    contact_info.append(resume_data["personal_info"]["location"])
    
    # First line: phone, email, location
    pdf.cell(0, 5, " | ".join(contact_info), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    
    # Second line: professional links
    links = []
    if resume_data["personal_info"]["linkedin"]:
        links.append("LinkedIn")
    if resume_data["personal_info"].get("github"):
        links.append("GitHub")
    if resume_data["personal_info"].get("portfolio"):
        links.append("Portfolio")
    
    if links:
        pdf.cell(0, 5, " | ".join(links), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    
    # Summary
    pdf.ln(10)
    pdf.set_font(pdf.font_family, 'B', 12)
    pdf.cell(0, 10, "Professional Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.font_family, '', 10)
    pdf.wrapped_cell(0, 5, resume_data["summary"])
    
    # Experience
    pdf.ln(5)
    pdf.set_font(pdf.font_family, 'B', 12)
    pdf.cell(0, 10, "Professional Experience", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    for exp in resume_data["experience"]:
        pdf.set_font(pdf.font_family, 'B', 10)
        pdf.wrapped_cell(0, 5, f"{exp['title']} at {exp['company']}")
        pdf.set_font(pdf.font_family, '', 10)
        pdf.wrapped_cell(0, 5, f"{exp['location']} | {exp['start_date']} - {exp['end_date']}")
        for resp in exp["responsibilities"]:
            pdf.wrapped_cell(0, 5, f"{pdf.bullet} {resp}")
        pdf.wrapped_cell(0, 5, f"Technologies: {', '.join(exp['technologies'])}")
        pdf.ln(3)  # Reduced spacing between experiences
    
    # Education
    pdf.ln(5)
    pdf.set_font(pdf.font_family, 'B', 12)
    pdf.cell(0, 10, "Education", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    for edu in resume_data["education"]:
        pdf.set_font(pdf.font_family, 'B', 10)
        pdf.wrapped_cell(0, 5, f"{edu['degree']} in {edu['field']}")
        pdf.set_font(pdf.font_family, '', 10)
        pdf.wrapped_cell(0, 5, f"{edu['university']} - {edu['location']} | {edu['year']}")
        pdf.wrapped_cell(0, 5, f"GPA: {edu['gpa']}")
        pdf.wrapped_cell(0, 5, f"Relevant Coursework: {', '.join(edu['relevant_coursework'])}")
        pdf.ln(3)  # Reduced spacing between education entries
    
    # Skills
    pdf.ln(5)
    pdf.set_font(pdf.font_family, 'B', 12)
    pdf.cell(0, 10, "Skills", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf.font_family, '', 10)
    pdf.format_skills(resume_data["skills"])
    
    # Certifications
    if resume_data.get("certifications"):
        pdf.ln(5)
        pdf.set_font(pdf.font_family, 'B', 12)
        pdf.cell(0, 10, "Certifications", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font(pdf.font_family, '', 10)
        for cert in resume_data["certifications"]:
            pdf.wrapped_cell(0, 5, f"{pdf.bullet} {cert}")
    
    try:
        # Add font info to the filename
        font_name = pdf.font_family.capitalize()
        base, ext = os.path.splitext(output_path)
        output_path = f"{base}_{font_name}{ext}"
        
        pdf.output(output_path)
        return True
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return False

def get_role_variations(num_resumes: int = 7) -> List[dict]:
    """Return a list of different role variations for diverse resumes"""
    # Base variations
    base_variations = [
        {
            'role': 'Software Engineer',
            'level': 'Mid-level',
            'focus': 'Full-stack development',
            'tech_stack': 'Python, JavaScript, React, and AWS',
            'years': '4-6'
        },
        {
            'role': 'Frontend Developer',
            'level': 'Senior',
            'focus': 'UI/UX implementation',
            'tech_stack': 'React, TypeScript, and modern CSS frameworks',
            'years': '6-8'
        },
        {
            'role': 'Backend Engineer',
            'level': 'Mid-Senior',
            'focus': 'distributed systems',
            'tech_stack': 'Java, Spring Boot, and Kubernetes',
            'years': '5-7'
        },
        {
            'role': 'DevOps Engineer',
            'level': 'Senior',
            'focus': 'cloud infrastructure and automation',
            'tech_stack': 'AWS, Terraform, and CI/CD pipelines',
            'years': '7-9'
        },
        {
            'role': 'Machine Learning Engineer',
            'level': 'Mid-level',
            'focus': 'ML model deployment',
            'tech_stack': 'Python, PyTorch, and MLOps tools',
            'years': '3-5'
        },
        {
            'role': 'Data Engineer',
            'level': 'Senior',
            'focus': 'data pipeline development',
            'tech_stack': 'Python, Spark, and cloud data services',
            'years': '6-8'
        },
        {
            'role': 'Mobile Developer',
            'level': 'Mid-Senior',
            'focus': 'iOS/Android development',
            'tech_stack': 'Swift, Kotlin, and React Native',
            'years': '5-7'
        }
    ]

    # If requested number is less than or equal to base variations, return random subset
    if num_resumes <= len(base_variations):
        return random.sample(base_variations, num_resumes)

    # For additional variations beyond base set, create variations with different levels and tech stacks
    levels = ['Junior', 'Mid-level', 'Senior', 'Lead', 'Principal']
    tech_stacks = [
        'Python, Django, and PostgreSQL',
        'Node.js, Express, and MongoDB',
        'Go, gRPC, and Redis',
        'Ruby, Rails, and MySQL',
        'Vue.js, Nuxt, and GraphQL',
        'Angular, TypeScript, and Firebase',
        'Rust, WebAssembly, and Docker',
        'Scala, Akka, and Apache Kafka',
        'PHP, Laravel, and MariaDB',
        'C#, .NET Core, and Azure'
    ]

    result = base_variations.copy()
    while len(result) < num_resumes:
        # Take a random base variation and modify it
        base = random.choice(base_variations)
        new_variation = base.copy()
        
        # Modify level and years
        new_level = random.choice(levels)
        years = '1-3' if new_level == 'Junior' else '4-6' if new_level == 'Mid-level' else '7-10' if new_level == 'Senior' else '10+'
        new_variation['level'] = new_level
        new_variation['years'] = years
        
        # Modify tech stack
        new_variation['tech_stack'] = random.choice(tech_stacks)
        
        result.append(new_variation)

    return result[:num_resumes]

def get_unique_name(used_names: set) -> str:
    """Generate a unique name that hasn't been used before"""
    first_names = [
        "James", "Emma", "Michael", "Sophia", "William", "Olivia", "Alexander", "Ava",
        "Daniel", "Isabella", "David", "Mia", "Joseph", "Charlotte", "Andrew", "Amelia",
        "John", "Harper", "Christopher", "Evelyn", "Matthew", "Abigail", "Joshua", "Emily",
        "Ryan", "Elizabeth", "Nathan", "Sofia", "Kevin", "Avery", "Justin", "Ella",
        "Brandon", "Scarlett", "Samuel", "Victoria", "Benjamin", "Madison", "Jonathan", "Luna",
        "Ethan", "Grace", "Aaron", "Chloe", "Adam", "Penelope", "Brian", "Layla",
        "Tyler", "Riley", "Zachary", "Zoey", "Scott", "Nora", "Jeremy", "Lily",
        "Stephen", "Eleanor", "Kyle", "Hannah", "Eric", "Lillian", "Peter", "Addison"
    ]
    
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
        "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
        "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
        "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
        "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
        "Carter", "Roberts", "Chen", "Zhang", "Kumar", "Singh", "Shah", "Patel",
        "Murphy", "Cook", "Rogers", "Morgan", "Peterson", "Cooper", "Reed", "Bailey"
    ]
    
    # Keep trying until we find a unique name
    while True:
        first = random.choice(first_names)
        last = random.choice(last_names)
        full_name = f"{first} {last}"
        if full_name not in used_names:
            used_names.add(full_name)
            return full_name

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
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(base_output_dir, f"attempt_{timestamp}")
        os.makedirs(output_dir)
        print(f"Created output directory for this run: {output_dir}")

        # Get role variations based on requested number
        variations = get_role_variations(args.num_resumes)
        num_resumes = len(variations)
        successful = 0
        
        # Keep track of used names to ensure uniqueness
        used_names = set()
        
        for i, variation in enumerate(variations):
            print(f"\nGenerating resume {i+1}/{num_resumes} for {variation['level']} {variation['role']}...")
            try:
                # Generate a unique name for this resume
                unique_name = get_unique_name(used_names)
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
                
                # Save as JSON
                json_path = os.path.join(output_dir, f"resume_{i}_{variation['role'].lower().replace(' ', '_')}.json")
                print(f"Saving JSON to: {json_path}")
                with open(json_path, 'w') as f:
                    json.dump(resume_data, f, indent=2)
                
                # Generate PDF
                pdf_path = os.path.join(output_dir, f"resume_{i}_{variation['role'].lower().replace(' ', '_')}.pdf")
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