import unittest
import os
import json
from pdf_generator import create_pdf

class TestPDFGenerator(unittest.TestCase):
    def setUp(self):
        # Sample resume data with minimal but complete structure
        self.test_resume_data = {
            "personal_info": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "123-456-7890",
                "location": "San Francisco, CA",
                "linkedin": "https://linkedin.com/in/testuser",
                "github": "https://github.com/testuser",
                "portfolio": "https://testuser.dev",  # Include portfolio for frontend role
                "blog": None
            },
            "summary": "Experienced frontend developer with focus on React and modern web technologies.",
            "experience": [
                {
                    "title": "Frontend Developer",
                    "company": "Test Company",
                    "location": "San Francisco, CA",
                    "start_date": "2020-01",
                    "end_date": "Present",
                    "achievements": [
                        "Reduced load time by 50%",
                        "Improved Lighthouse score to 98"
                    ],
                    "responsibilities": [
                        "Developed responsive web applications using React",
                        "Implemented design systems and component libraries"
                    ],
                    "technologies": ["React", "TypeScript", "Webpack"],
                    "projects": [
                        {
                            "name": "Design System Implementation",
                            "description": "Created a company-wide design system",
                            "metrics": ["Reduced development time by 40%"],
                            "technologies": ["React", "Storybook"],
                            "duration": "6 months",
                            "role": "Tech Lead",
                            "link": "https://design.testcompany.com"
                        }
                    ]
                }
            ],
            "education": [
                {
                    "degree": "B.S.",
                    "field": "Computer Science",
                    "university": "Test University",
                    "location": "San Francisco, CA",
                    "year": 2019,
                    "gpa": 3.8,
                    "relevant_coursework": [
                        "Web Development",
                        "UI/UX Design",
                        "Human-Computer Interaction"
                    ],
                    "thesis": None,
                    "honors": ["Dean's List"]
                }
            ],
            "skills": [
                {
                    "category": "UI Frameworks",
                    "skills": ["React", "Vue", "Angular"],
                    "proficiency_level": "Expert"
                },
                {
                    "category": "Tools & Technologies",
                    "skills": ["Git", "Webpack", "Jest"],
                    "proficiency_level": "Advanced"
                }
            ],
            "certifications": [
                "AWS Certified Developer"
            ],
            "awards": [
                "Employee of the Year 2022"
            ],
            "languages": [
                {"language": "English", "proficiency": "Native"},
                {"language": "Spanish", "proficiency": "Intermediate"}
            ]
        }
        
        # Create test output directory
        self.test_output_dir = "test_output"
        if not os.path.exists(self.test_output_dir):
            os.makedirs(self.test_output_dir)
            
    def tearDown(self):
        # Clean up test files
        test_pdf = os.path.join(self.test_output_dir, "test_resume.pdf")
        if os.path.exists(test_pdf):
            os.remove(test_pdf)
        if os.path.exists(self.test_output_dir):
            os.rmdir(self.test_output_dir)

    def test_pdf_generation_basic(self):
        """Test basic PDF generation with minimal resume data"""
        output_path = os.path.join(self.test_output_dir, "test_resume.pdf")
        result = create_pdf(self.test_resume_data, output_path, "frontend_developer")
        
        # Check if PDF was created successfully
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_path))
        self.assertTrue(os.path.getsize(output_path) > 0)

    def test_pdf_generation_with_special_chars(self):
        """Test PDF generation with special characters"""
        # Modify test data to include special characters
        test_data = self.test_resume_data.copy()
        test_data["personal_info"]["name"] = "Tést Üser"
        test_data["summary"] = "Experience with © and ™ symbols"
        
        output_path = os.path.join(self.test_output_dir, "test_resume.pdf")
        result = create_pdf(test_data, output_path, "frontend_developer")
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_path))
        self.assertTrue(os.path.getsize(output_path) > 0)

    def test_pdf_generation_with_long_text(self):
        """Test PDF generation with very long text fields"""
        test_data = self.test_resume_data.copy()
        test_data["summary"] = "A" * 1000  # Very long summary
        test_data["experience"][0]["description"] = "B" * 500  # Long description
        
        output_path = os.path.join(self.test_output_dir, "test_resume.pdf")
        result = create_pdf(test_data, output_path, "frontend_developer")
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_path))
        self.assertTrue(os.path.getsize(output_path) > 0)

    def test_pdf_generation_with_missing_optional_fields(self):
        """Test PDF generation with missing optional fields"""
        test_data = self.test_resume_data.copy()
        # Remove optional fields
        test_data["certifications"] = None
        test_data["awards"] = None
        test_data["languages"] = None
        
        output_path = os.path.join(self.test_output_dir, "test_resume.pdf")
        result = create_pdf(test_data, output_path, "frontend_developer")
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_path))
        self.assertTrue(os.path.getsize(output_path) > 0)

def flatten_skills(skills_data):
    """Convert the structured skills data into a flat list of skills"""
    flattened = []
    for skill_category in skills_data:
        if isinstance(skill_category.get('skills'), list):
            flattened.extend(skill_category['skills'])
    return flattened

def test_pdf_generation():
    # Use the specific resume file path
    json_path = "/Users/lilyzhang/Documents/Development/neetcode_2025/curator/examples/synthetic_resume/generated_resumes/attempt_20250126_123906/resume_emily_chen_data_engineer.json"
    # Generate output PDF in the same directory
    output_pdf_path = json_path.replace('.json', '.pdf')
    
    try:
        with open(json_path, 'r') as f:
            resume_data = json.load(f)
        
        # Flatten the skills structure
        if isinstance(resume_data.get('skills', []), list):
            resume_data['skills'] = flatten_skills(resume_data['skills'])
        
        # Create PDF with role title
        success = create_pdf(resume_data, output_pdf_path, "Data Engineer")
        
        if success:
            print(f"PDF successfully generated at: {output_pdf_path}")
            print(f"File size: {os.path.getsize(output_pdf_path)} bytes")
        else:
            print("Failed to generate PDF")
            
    except FileNotFoundError:
        print(f"Error: Could not find file {json_path}")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {json_path}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_pdf_generation() 