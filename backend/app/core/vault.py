import os
from dotenv import load_dotenv

load_dotenv()

class Vault:
    @staticmethod
    def get_secret(key: str, default: str = None) -> str:
        return os.getenv(key, default)

vault = Vault()
