import random

class NameGenerator:
    """Utility class for generating unique names"""
    
    def __init__(self):
        self.first_names = [
            "James", "Emma", "Michael", "Sophia", "William", "Olivia", "Alexander", "Ava",
            "Daniel", "Isabella", "David", "Mia", "Joseph", "Charlotte", "Andrew", "Amelia",
            "John", "Harper", "Christopher", "Evelyn", "Matthew", "Abigail", "Joshua", "Emily",
            "Ryan", "Elizabeth", "Nathan", "Sofia", "Kevin", "Avery", "Justin", "Ella",
            "Brandon", "Scarlett", "Samuel", "Victoria", "Benjamin", "Madison", "Jonathan", "Luna",
            "Ethan", "Grace", "Aaron", "Chloe", "Adam", "Penelope", "Brian", "Layla",
            "Tyler", "Riley", "Zachary", "Zoey", "Scott", "Nora", "Jeremy", "Lily",
            "Stephen", "Eleanor", "Kyle", "Hannah", "Eric", "Lillian", "Peter", "Addison"
        ]
        
        self.last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
            "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
            "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
            "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
            "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
            "Carter", "Roberts", "Chen", "Zhang", "Kumar", "Singh", "Shah", "Patel",
            "Murphy", "Cook", "Rogers", "Morgan", "Peterson", "Cooper", "Reed", "Bailey"
        ]
        self.used_names = set()
    
    def get_unique_name(self) -> str:
        """Generate a unique name that hasn't been used before"""
        while True:
            first = random.choice(self.first_names)
            last = random.choice(self.last_names)
            full_name = f"{first} {last}"
            if full_name not in self.used_names:
                self.used_names.add(full_name)
                return full_name 