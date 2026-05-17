from pydantic_settings import BaseSettings
from functools import lru_cache
from backend.app.core.vault import vault

class Settings(BaseSettings):
    PROJECT_NAME: str = "Code-Realme-NonStoP"
    SECRET_KEY: str = vault.get_secret("SECRET_KEY", "CHANGEME")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = vault.get_secret("DATABASE_URL", "sqlite:///./sql_app.db")

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
