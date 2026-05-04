import random


class StealthConfig:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119 Safari/537.36"
        ]
        self.timezones = ["Europe/Warsaw", "Europe/Berlin"]
        self.locales = ["en-US", "en-GB"]

    def random_ua(self):
        return random.choice(self.user_agents)

    def random_timezone(self):
        return random.choice(self.timezones)

    def random_locale(self):
        return random.choice(self.locales)
