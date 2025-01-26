from typing import Dict, Tuple

FONT_STYLES = {
    "modern": {
        "name": "helvetica",
        "header_size": 14,
        "section_size": 12,
        "body_size": 10,
        "spacing": 5,
    },
    "classic": {
        "name": "times",
        "header_size": 16,
        "section_size": 13,
        "body_size": 11,
        "spacing": 5,
    },
    "minimal": {
        "name": "arial",
        "header_size": 14,
        "section_size": 11,
        "body_size": 10,
        "spacing": 4,
    },
    "professional": {
        "name": "helvetica",
        "header_size": 15,
        "section_size": 12,
        "body_size": 10,
        "spacing": 5,
    },
    "academic": {
        "name": "times",
        "header_size": 14,
        "section_size": 12,
        "body_size": 11,
        "spacing": 6,
    }
}

def get_font_style(role: str) -> Dict:
    """Return appropriate font style based on role"""
    role = role.lower()
    
    if any(term in role for term in ['researcher', 'scientist', 'phd', 'professor']):
        return FONT_STYLES["academic"]
    elif any(term in role for term in ['senior', 'lead', 'principal', 'architect']):
        return FONT_STYLES["professional"]
    elif any(term in role for term in ['ui', 'ux', 'designer', 'creative']):
        return FONT_STYLES["modern"]
    elif any(term in role for term in ['engineer', 'developer']):
        return FONT_STYLES["minimal"]
    else:
        return FONT_STYLES["classic"] 