import os
import logging
from datetime import datetime
import json
import re
from typing import Optional
from role_generator import RoleGenerator
from resume_generator import ResumeGenerator
from name_generator import NameGenerator
from pdf_generator import create_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResumeGenerationOrchestrator:
    """Orchestrates the resume generation process"""
    
    def __init__(self):
        self.role_generator = RoleGenerator()
        self.resume_generator = ResumeGenerator()
        self.name_generator = NameGenerator()
        
        # Create base output directory
        self.base_dir = "generated_resumes"
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Create timestamped directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(self.base_dir, f"attempt_{timestamp}")
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Created output directory: {self.output_dir}")
    
    def generate_resumes(self, num_resumes: int = 5) -> None:
        """Generate specified number of resumes"""
        successful = 0
        try:
            variations = self.role_generator.get_variations(num_resumes)
            
            for i, variation in enumerate(variations, 1):
                try:
                    unique_name = self.name_generator.get_unique_name()
                    variation['name'] = unique_name
                    
                    resume_data = self.resume_generator([{'role_variation': variation}])
                    if not resume_data or len(resume_data) == 0:
                        logger.error(f"No data generated for resume {i}")
                        continue
                    
                    resume = resume_data[0]
                    resume["personal_info"]["name"] = unique_name
                    
                    # Generate filenames
                    safe_name = self._get_safe_filename(unique_name)
                    role_name = self._get_safe_filename(variation['role'])
                    
                    # Save files
                    if self._save_resume_files(resume, safe_name, role_name):
                        successful += 1
                        
                except Exception as e:
                    logger.error(f"Error generating resume {i}: {str(e)}")
                    continue
                
        except Exception as e:
            logger.error(f"Error in resume generation: {str(e)}")
            raise
        finally:
            logger.info(f"\nGeneration complete!")
            logger.info(f"Successfully generated {successful} out of {num_resumes} resumes")
            logger.info(f"Files are saved in: {self.output_dir}")

    def _get_safe_filename(self, text: str) -> str:
        """Generate safe filename from text"""
        return re.sub(r'[^a-z0-9_]', '', text.lower().replace(' ', '_'))

    def _save_resume_files(self, resume: dict, safe_name: str, role_name: str) -> bool:
        """Save resume files and return success status"""
        try:
            # Save JSON
            json_path = os.path.join(self.output_dir, f"resume_{safe_name}_{role_name}.json")
            with open(json_path, 'w') as f:
                json.dump(resume, f, indent=2)
            logger.info(f"Saved JSON to: {json_path}")
            
            # Generate PDF
            pdf_path = os.path.join(self.output_dir, f"resume_{safe_name}_{role_name}.pdf")
            if create_pdf(resume, pdf_path):
                logger.info(f"Created PDF: {pdf_path}")
                return True
                
            logger.error("Failed to create PDF")
            return False
            
        except Exception as e:
            logger.error(f"Error saving files: {str(e)}")
            return False

def main():
    """Main entry point"""
    import argparse
    parser = argparse.ArgumentParser(description='Generate synthetic resumes')
    parser.add_argument('--num', type=int, default=5, help='Number of resumes to generate')
    args = parser.parse_args()
    
    orchestrator = ResumeGenerationOrchestrator()
    orchestrator.generate_resumes(num_resumes=args.num)

if __name__ == "__main__":
    main() 