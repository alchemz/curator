import random
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os
from typing import Dict, Any
import re

class ResumePDF(FPDF):
    """Custom PDF class for resume generation"""
    
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

    def sanitize_text(self, text: str) -> str:
        """Sanitize text to handle special characters"""
        # Replace common special characters with ASCII alternatives
        replacements = {
            '–': '-',  # en dash
            '—': '-',  # em dash
            '"': '"',  # curly quotes
            '"': '"',
            ''': "'",  # curly apostrophes
            ''': "'",
            '•': '-',  # bullet points
            '…': '...',  # ellipsis
            '©': '(c)',
            '®': '(R)',
            '™': '(TM)',
            '°': 'deg',
            '±': '+/-',
            '×': 'x',
            '÷': '/',
            '≤': '<=',
            '≥': '>=',
            '≠': '!=',
            '∞': 'inf',
            '′': "'",
            '″': '"',
            '\u200b': '',  # zero-width space
            '\u200e': '',  # left-to-right mark
            '\u200f': '',  # right-to-left mark
            '\ufeff': '',  # zero-width no-break space
        }
        
        # Apply all replacements
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Replace any remaining non-ASCII characters with their closest ASCII equivalent
        text = text.encode('ascii', 'replace').decode()
        text = text.replace('?', '')  # Remove the replacement character
        
        return text

    def header(self):
        """Custom header with consistent font family"""
        self.set_font(self.font_family)

    def wrapped_cell(self, w, h, txt, border=0, align='L', new_x=XPos.LMARGIN, new_y=YPos.NEXT):
        """Custom cell with text wrapping"""
        # Sanitize text before processing
        txt = self.sanitize_text(txt)
        
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
        # Sanitize all skills first
        skills = [self.sanitize_text(skill) for skill in skills]
        
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
    pdf = ResumePDF()
    pdf.add_page()
    
    # Name
    candidate_name = resume_data["personal_info"]["name"]
    pdf.set_font(pdf.font_family, 'B', 16)
    pdf.cell(0, 10, pdf.sanitize_text(candidate_name), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    
    # Contact info on one line with separators
    pdf.set_font(pdf.font_family, '', 10)
    contact_info = []
    
    # Phone and email
    contact_info.append(pdf.sanitize_text(resume_data["personal_info"]["phone"]))
    contact_info.append(pdf.sanitize_text(resume_data["personal_info"]["email"]))
    contact_info.append(pdf.sanitize_text(resume_data["personal_info"]["location"]))
    
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
        pdf.wrapped_cell(0, 5, f"{pdf.sanitize_text(exp['title'])} at {pdf.sanitize_text(exp['company'])}")
        pdf.set_font(pdf.font_family, '', 10)
        pdf.wrapped_cell(0, 5, f"{pdf.sanitize_text(exp['location'])} | {pdf.sanitize_text(exp['start_date'])} - {pdf.sanitize_text(exp['end_date'])}")
        for resp in exp["responsibilities"]:
            pdf.wrapped_cell(0, 5, f"{pdf.bullet} {pdf.sanitize_text(resp)}")
        pdf.wrapped_cell(0, 5, f"Technologies: {', '.join(pdf.sanitize_text(tech) for tech in exp['technologies'])}")
        pdf.ln(3)  # Reduced spacing between experiences
    
    # Education
    pdf.ln(5)
    pdf.set_font(pdf.font_family, 'B', 12)
    pdf.cell(0, 10, "Education", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    for edu in resume_data["education"]:
        pdf.set_font(pdf.font_family, 'B', 10)
        pdf.wrapped_cell(0, 5, f"{pdf.sanitize_text(edu['degree'])} in {pdf.sanitize_text(edu['field'])}")
        pdf.set_font(pdf.font_family, '', 10)
        pdf.wrapped_cell(0, 5, f"{pdf.sanitize_text(edu['university'])} - {pdf.sanitize_text(edu['location'])} | {edu['year']}")
        pdf.wrapped_cell(0, 5, f"GPA: {edu['gpa']}")
        pdf.wrapped_cell(0, 5, f"Relevant Coursework: {', '.join(pdf.sanitize_text(course) for course in edu['relevant_coursework'])}")
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
            pdf.wrapped_cell(0, 5, f"{pdf.bullet} {pdf.sanitize_text(cert)}")
    
    try:
        # Output the PDF directly with the provided path
        pdf.output(output_path)
        return True
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return False 