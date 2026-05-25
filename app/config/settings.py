from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FERNET_SECRET_KEY: str
    
    # AI Provider
    GEMINI_API_KEY: str
    
    # Model Config
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """
    Caches and returns the application settings.
    Using lru_cache ensures we only read the .env file once.
    """
    return Settings()