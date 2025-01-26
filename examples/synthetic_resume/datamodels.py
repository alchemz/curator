from typing import List, Optional
from pydantic import BaseModel, Field

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