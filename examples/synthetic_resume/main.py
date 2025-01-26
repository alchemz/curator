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
        try:
            # Generate role variations
            logger.info(f"Generating {num_resumes} role variations...")
            variations = self.role_generator.get_variations(num_resumes)
            
            successful = 0
            # Generate resumes for each role
            for i, variation in enumerate(variations, 1):
                logger.info(f"Generating resume {i}/{num_resumes} for {variation['level']} {variation['role']}...")
                try:
                    # Generate unique name
                    unique_name = self.name_generator.get_unique_name()
                    variation['name'] = unique_name
                    
                    # Generate resume content
                    resume_data = self.resume_generator([{'role_variation': variation}])
                    
                    if not resume_data or len(resume_data) == 0:
                        logger.error(f"No data generated for resume {i}")
                        continue
                    
                    # Extract resume data
                    resume = resume_data[0]
                    
                    # Ensure generated resume uses the unique name
                    resume["personal_info"]["name"] = unique_name
                    
                    # Create safe filenames
                    safe_name = unique_name.lower().replace(' ', '_')
                    safe_name = re.sub(r'[^a-z0-9_]', '', safe_name)
                    role_name = variation['role'].lower().replace(' ', '_')
                    
                    # Save JSON
                    json_path = os.path.join(self.output_dir, f"resume_{safe_name}_{role_name}.json")
                    with open(json_path, 'w') as f:
                        json.dump(resume, f, indent=2)
                    logger.info(f"Saved JSON to: {json_path}")
                    
                    # Generate PDF
                    pdf_path = os.path.join(self.output_dir, f"resume_{safe_name}_{role_name}.pdf")
                    if create_pdf(resume, pdf_path):
                        logger.info(f"Created PDF: {pdf_path}")
                        successful += 1
                    else:
                        logger.error(f"Failed to create PDF for resume {i}")
                    
                except Exception as e:
                    logger.error(f"Error generating resume {i}: {str(e)}")
                    continue
            
            # Print summary
            logger.info(f"\nGeneration complete!")
            logger.info(f"Successfully generated {successful} out of {num_resumes} resumes")
            logger.info(f"Files are saved in: {self.output_dir}")
            
        except Exception as e:
            logger.error(f"Error in resume generation: {str(e)}")
            raise

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