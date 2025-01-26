import random
from typing import List, Dict

class RoleGenerator:
    """Utility class for generating role variations"""
    
    def __init__(self):
        self.base_variations = [
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
        
        self.levels = ['Junior', 'Mid-level', 'Senior', 'Lead', 'Principal']
        self.tech_stacks = [
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

    def get_variations(self, num_resumes: int = 7) -> List[Dict]:
        """Return a list of different role variations for diverse resumes"""
        # If requested number is less than or equal to base variations, return random subset
        if num_resumes <= len(self.base_variations):
            return random.sample(self.base_variations, num_resumes)

        # For additional variations beyond base set, create variations with different levels and tech stacks
        result = self.base_variations.copy()
        while len(result) < num_resumes:
            # Take a random base variation and modify it
            base = random.choice(self.base_variations)
            new_variation = base.copy()
            
            # Modify level and years
            new_level = random.choice(self.levels)
            years = '1-3' if new_level == 'Junior' else '4-6' if new_level == 'Mid-level' else '7-10' if new_level == 'Senior' else '10+'
            new_variation['level'] = new_level
            new_variation['years'] = years
            
            # Modify tech stack
            new_variation['tech_stack'] = random.choice(self.tech_stacks)
            
            result.append(new_variation)

        return result[:num_resumes] 