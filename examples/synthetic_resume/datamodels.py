from typing import List, Optional, Dict, Any
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

class Certification(BaseModel):
    """Certification entry"""
    name: str = Field(description="Name of certification")
    issuer: str = Field(description="Issuing organization")
    date: str = Field(description="Date of certification")

class Resume(BaseModel):
    """Complete resume structure with dynamic sections"""
    personal_info: PersonalInfo = Field(description="Personal and contact information")
    summary: str = Field(description="Professional summary")
    experience: List[Experience] = Field(description="Work experience entries")
    education: List[Education] = Field(description="Education entries")
    skills: List[str] = Field(description="List of technical and professional skills")
    
    # Make all these truly optional
    publications: Optional[List[Dict[str, Any]]] = Field(None, description="Academic publications")
    certifications: Optional[List[Dict[str, Any]]] = Field(None, description="Professional certifications")
    awards: Optional[List[str]] = Field(None, description="Professional awards and recognition")
    languages: Optional[List[Dict[str, str]]] = Field(None, description="Language proficiencies")
    projects: Optional[List[Dict[str, Any]]] = Field(None, description="Research project details")
    portfolio: Optional[List[Dict[str, Any]]] = Field(None, description="Portfolio projects")
    open_source: Optional[List[Dict[str, Any]]] = Field(None, description="Open source contributions")
    system_architecture: Optional[List[Dict[str, Any]]] = Field(None, description="System architecture experience")
    infrastructure: Optional[List[Dict[str, Any]]] = Field(None, description="Infrastructure and DevOps experience")
    security: Optional[List[Dict[str, Any]]] = Field(None, description="Security expertise")
    app_store: Optional[List[Dict[str, Any]]] = Field(None, description="App store publications")
    volunteer: Optional[List[Dict[str, Any]]] = Field(None, description="Volunteer work")

    class Config:
        extra = "allow" 