import unittest
from unittest.mock import patch, MagicMock
import json
import os
from resume_generator import ResumeGenerator, main
from datamodels import Resume

class TestResumeGenerator(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        # Mock environment variable
        os.environ['DEEPSEEK_API_KEY'] = 'test_key'
        self.generator = ResumeGenerator()
        
        # Sample role variation for testing
        self.test_role = {
            'role': 'Software Engineer',
            'level': 'Mid-level',
            'focus': 'Full-stack development',
            'tech_stack': 'Python, JavaScript, and cloud technologies',
            'years': '4-6'
        }
        
        # Sample LLM response
        self.sample_response = {
            "choices": [{
                "message": {
                    "content": '''{
                        "personal_info": {
                            "name": "Test User",
                            "email": "test@example.com",
                            "phone": "123-456-7890",
                            "location": "San Francisco, CA",
                            "linkedin": "linkedin.com/in/testuser",
                            "github": "github.com/testuser",
                            "portfolio": "testuser.dev"
                        },
                        "summary": "Experienced software engineer with focus on full-stack development",
                        "experience": [{
                            "title": "Software Engineer",
                            "company": "Tech Corp",
                            "location": "San Francisco, CA",
                            "start_date": "2020-01",
                            "end_date": "Present",
                            "responsibilities": [
                                "Developed full-stack applications",
                                "Led team projects"
                            ],
                            "technologies": ["Python", "JavaScript", "AWS"]
                        }],
                        "education": [{
                            "degree": "B.S.",
                            "field": "Computer Science",
                            "university": "Test University",
                            "location": "San Francisco, CA",
                            "year": 2019,
                            "gpa": 3.8,
                            "relevant_coursework": [
                                "Data Structures",
                                "Algorithms"
                            ]
                        }],
                        "skills": [
                            {
                                "category": "Programming Languages",
                                "skills": ["Python", "JavaScript"],
                                "proficiency_level": "Expert"
                            }
                        ],
                        "certifications": ["AWS Certified Developer"],
                        "awards": ["Best Team Player 2022"],
                        "languages": [
                            {"language": "English", "proficiency": "Native"}
                        ]
                    }'''
                }
            }]
        }

    def test_init(self):
        """Test ResumeGenerator initialization"""
        self.assertEqual(self.generator.model_name, "deepseek-reasoner")
        self.assertEqual(self.generator.generation_params["temperature"], 0.7)
        self.assertEqual(self.generator.generation_params["max_tokens"], 2048)

    def test_prompt_generation(self):
        """Test prompt generation with role variation"""
        prompts = self.generator.prompt({"role_variation": self.test_role})
        
        # Check if prompts is a list with system and user messages
        self.assertIsInstance(prompts, list)
        self.assertEqual(len(prompts), 2)
        
        # Check message structure
        self.assertEqual(prompts[0]["role"], "system")
        self.assertEqual(prompts[1]["role"], "user")
        
        # Check if role variation is included in user prompt
        user_prompt = prompts[1]["content"]
        self.assertIn(self.test_role["role"], user_prompt)
        self.assertIn(self.test_role["level"], user_prompt)

    @patch('resume_generator.ResumeGenerator.__call__')
    def test_resume_generation(self, mock_call):
        """Test full resume generation process"""
        # Mock the LLM call
        mock_call.return_value = [self.sample_response]
        
        # Generate resume
        result = self.generator([{"role_variation": self.test_role}])
        
        # Verify the result
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        
        resume_data = result[0]
        self.assertIn("personal_info", resume_data)
        self.assertIn("experience", resume_data)
        self.assertIn("education", resume_data)
        self.assertIn("skills", resume_data)

    def test_parse_response(self):
        """Test parsing of LLM response"""
        # Test parsing with valid response
        parsed = self.generator.parse({}, self.sample_response)
        
        # Verify parsed data structure
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed["personal_info"]["name"], "Test User")
        self.assertEqual(len(parsed["experience"]), 1)
        self.assertEqual(len(parsed["education"]), 1)

    def test_empty_input_handling(self):
        """Test handling of empty input"""
        result = self.generator.prompt({})
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)  # Should still return system and user prompts

    @patch('resume_generator.create_pdf')
    @patch('resume_generator.RoleGenerator')
    def test_main_function(self, mock_role_generator, mock_create_pdf):
        """Test main function execution"""
        # Mock role generator
        mock_role_generator.return_value.get_variations.return_value = [self.test_role]
        
        # Mock PDF creation
        mock_create_pdf.return_value = True
        
        # Mock argparse
        with patch('argparse.ArgumentParser.parse_args') as mock_args:
            mock_args.return_value = MagicMock(num_resumes=1)
            
            # Run main function
            try:
                main()
            except Exception as e:
                self.fail(f"main() raised an exception: {str(e)}")

if __name__ == '__main__':
    unittest.main() 