import random
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os
from typing import Dict, Any
import re
from font_config import get_font_style

class ResumePDF(FPDF):
    """Custom PDF class for resume generation"""
    
    def __init__(self, font_style: Dict):
        super().__init__()
        self.font_style = font_style
        
        # Map font names to FPDF built-in fonts
        font_mapping = {
            'helvetica': 'helvetica',
            'times': 'times',
            'arial': 'helvetica',  # Use helvetica as fallback for arial
        }
        
        self.font_family = font_mapping.get(font_style["name"].lower(), 'helvetica')
        self.bullet = '-'  # Simple dash for bullet points
        
        # Set default font
        self.set_font(self.font_family)
        
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)

    def sanitize_text(self, text: str) -> str:
        """Sanitize text to handle special characters"""
        if not isinstance(text, str):
            text = str(text)
        
        # Only replace specific problematic characters
        replacements = {
            '•': '-',  # bullet to dash
            '–': '-',  # en dash
            '—': '-',  # em dash
            '"': '"',  # smart quotes
            '"': '"',  # smart quotes
            ''': "'",  # smart quotes
            ''': "'",  # smart quotes
            '…': '...',  # ellipsis
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text

    def header(self):
        """Custom header with consistent font family"""
        self.set_font(self.font_family)

    def wrapped_cell(self, w: float, h: float, txt: str, border: int = 0, align: str = 'L', fill: bool = False):
        """Add a wrapped cell with sanitized text"""
        # Get the current position
        x = self.get_x()
        y = self.get_y()
        
        # Sanitize the text before processing
        txt = self.sanitize_text(txt)
        
        # Calculate wrapped lines
        lines = self.multi_cell(w, h, txt, border, align, fill, split_only=True)
        
        # Print each line
        for i, line in enumerate(lines):
            self.set_xy(x, y + i*h)
            if i == len(lines) - 1:
                self.cell(w, h, line, 0, 1, align)
            else:
                self.cell(w, h, line, 0, 2, align)

    def format_skills(self, skills):
        """Format skills into columns for better space usage"""
        # Handle case where skills is already a flat list of strings
        if skills and isinstance(skills[0], str):
            # Sanitize all skills
            skills = [self.sanitize_text(skill) for skill in skills]
        # Handle structured skills case
        elif skills and isinstance(skills[0], dict):
            flattened_skills = []
            for category in skills:
                if isinstance(category, dict):
                    if 'items' in category:
                        flattened_skills.extend(category['items'])
                    elif 'skills' in category:
                        flattened_skills.extend(category['skills'])
            skills = [self.sanitize_text(skill) for skill in flattened_skills]
        
        # For Courier font, use fewer columns due to wider characters
        num_columns = 2 if self.font_family == 'courier' else 3
        
        # Split skills into roughly equal columns
        skills_per_column = (len(skills) + num_columns - 1) // num_columns
        columns = []
        for i in range(0, len(skills), skills_per_column):
            columns.append(skills[i:i + skills_per_column])
        
        return columns

    def add_dynamic_section(self, title: str, content: Any):
        """Add a dynamic section to the resume"""
        self.ln(5)
        self.set_font(self.font_family, 'B', 12)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font(self.font_family, '', 10)
        
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    for key, value in item.items():
                        self.wrapped_cell(0, 5, f"{key}: {value}")
                else:
                    self.wrapped_cell(0, 5, f"{self.bullet} {item}")
        elif isinstance(content, dict):
            for key, value in content.items():
                self.wrapped_cell(0, 5, f"{key}: {value}")
        else:
            self.wrapped_cell(0, 5, str(content))

def create_pdf(resume_data: Dict, output_path: str) -> bool:
    """Create a PDF version of the resume"""
    # Get font style based on role
    role = resume_data.get("experience", [{}])[0].get("title", "Software Engineer")
    font_style = get_font_style(role)
    
    pdf = ResumePDF(font_style)
    pdf.add_page()
    
    # Personal Information - Name
    pdf.set_font(pdf.font_family, 'B', font_style["header_size"])
    pdf.cell(0, 10, resume_data["personal_info"]["name"], align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Contact Information - Split into two lines if needed
    pdf.set_font(pdf.font_family, '', font_style["body_size"])
    
    # First line: Email, Phone, Location
    line1_items = [
        resume_data["personal_info"]["email"],
        resume_data["personal_info"]["phone"],
        resume_data["personal_info"]["location"]
    ]
    pdf.cell(0, 5, " | ".join(line1_items), align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Second line: LinkedIn, GitHub, Portfolio
    line2_items = []
    if resume_data["personal_info"].get("linkedin"):
        line2_items.append(resume_data["personal_info"]["linkedin"])
    if resume_data["personal_info"].get("github"):
        line2_items.append(resume_data["personal_info"]["github"])
    if resume_data["personal_info"].get("portfolio"):
        line2_items.append(resume_data["personal_info"]["portfolio"])
    
    if line2_items:
        pdf.cell(0, 5, " | ".join(line2_items), align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Summary
    if resume_data.get("summary"):
        pdf.ln(3)
        pdf.set_font(pdf.font_family, 'B', font_style["section_size"])
        pdf.cell(0, 8, "Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font(pdf.font_family, '', font_style["body_size"])
        pdf.wrapped_cell(0, 5, resume_data["summary"])
    
    # Experience
    if resume_data.get("experience"):
        pdf.ln(3)
        pdf.set_font(pdf.font_family, 'B', font_style["section_size"])
        pdf.cell(0, 8, "Experience", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        for exp in resume_data["experience"]:
            pdf.set_font(pdf.font_family, 'B', font_style["body_size"])
            pdf.cell(0, 5, f"{exp['title']} - {exp['company']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font(pdf.font_family, 'I', font_style["body_size"])
            pdf.cell(0, 5, f"{exp['location']} | {exp['start_date']} - {exp['end_date']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font(pdf.font_family, '', font_style["body_size"])
            
            for resp in exp["responsibilities"]:
                pdf.wrapped_cell(0, 5, f"{pdf.bullet} {resp}")
            
            if exp.get("technologies"):
                pdf.wrapped_cell(0, 5, f"Technologies: {', '.join(exp['technologies'])}")
            pdf.ln(2)  # Small space between experiences
    
    # Education
    if resume_data.get("education"):
        pdf.ln(3)
        pdf.set_font(pdf.font_family, 'B', font_style["section_size"])
        pdf.cell(0, 8, "Education", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        for edu in resume_data["education"]:
            pdf.set_font(pdf.font_family, 'B', font_style["body_size"])
            pdf.cell(0, 5, f"{edu['degree']} in {edu['field']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font(pdf.font_family, 'I', font_style["body_size"])
            pdf.cell(0, 5, f"{edu['university']} | {edu['location']} | {edu['year']} | GPA: {edu['gpa']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font(pdf.font_family, '', font_style["body_size"])
            if edu.get("relevant_coursework"):
                pdf.wrapped_cell(0, 5, f"Relevant Coursework: {', '.join(edu['relevant_coursework'])}")
            pdf.ln(2)  # Small space between education entries
    
    # Skills
    if resume_data.get("skills"):
        pdf.ln(3)
        pdf.set_font(pdf.font_family, 'B', font_style["section_size"])
        pdf.cell(0, 8, "Skills", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # Set font for skills
        pdf.set_font(pdf.font_family, '', font_style["body_size"])
        
        # Join all skills with commas
        skills_text = ", ".join(resume_data["skills"])
        
        # Handle long skill lists with wrapping
        words = skills_text.split(", ")
        current_line = []
        
        for word in words:
            current_line.append(word)
            test_line = ", ".join(current_line)
            if pdf.get_string_width(test_line) > (pdf.w - pdf.l_margin - pdf.r_margin):
                # Print current line and start new one
                pdf.cell(0, 5, ", ".join(current_line[:-1]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                current_line = [word]
        
        # Print remaining skills
        if current_line:
            pdf.cell(0, 5, ", ".join(current_line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        pdf.ln(1)  # Small space after skills section
    
    # Publications for ML/AI roles
    if resume_data.get("publications"):
        pdf.ln(3)
        pdf.set_font(pdf.font_family, 'B', font_style["section_size"])
        pdf.cell(0, 8, "Publications", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        for pub in resume_data["publications"]:
            if isinstance(pub, dict):
                pdf.set_font(pdf.font_family, 'B', font_style["body_size"])
                pdf.wrapped_cell(0, 5, f"{pdf.bullet} {pdf.sanitize_text(pub['title'])}")
                pdf.set_font(pdf.font_family, '', font_style["body_size"])
                if pub.get("authors"):
                    pdf.wrapped_cell(0, 5, f"    Authors: {pdf.sanitize_text(', '.join(pub['authors']))}")
                if pub.get("journal"):
                    pdf.wrapped_cell(0, 5, f"    {pdf.sanitize_text(pub['journal'])} ({pub.get('year', '')})")
                if pub.get("link"):
                    pdf.wrapped_cell(0, 5, f"    Link: {pdf.sanitize_text(pub['link'])}")
            else:
                pdf.wrapped_cell(0, 5, f"{pdf.bullet} {pdf.sanitize_text(str(pub))}")
            pdf.ln(2)  # Small space between publications
    
    # Research Projects
    if resume_data.get("research_projects"):
        pdf.ln(3)
        pdf.set_font(pdf.font_family, 'B', font_style["section_size"])
        pdf.cell(0, 8, "Research Projects", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        for project in resume_data["research_projects"]:
            if isinstance(project, dict):
                pdf.set_font(pdf.font_family, 'B', font_style["body_size"])
                pdf.wrapped_cell(0, 5, f"{pdf.bullet} {pdf.sanitize_text(project['title'])}")
                pdf.set_font(pdf.font_family, '', font_style["body_size"])
                if project.get("description"):
                    pdf.wrapped_cell(0, 5, f"    {pdf.sanitize_text(project['description'])}")
                if project.get("technologies"):
                    pdf.wrapped_cell(0, 5, f"    Technologies: {pdf.sanitize_text(', '.join(project['technologies']))}")
                if project.get("results"):
                    for result in project["results"]:
                        pdf.wrapped_cell(0, 5, f"    - {pdf.sanitize_text(result)}")
            else:
                pdf.wrapped_cell(0, 5, f"{pdf.bullet} {pdf.sanitize_text(str(project))}")
            pdf.ln(2)  # Small space between projects
    
    try:
        pdf.output(output_path)
        return True
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return False 