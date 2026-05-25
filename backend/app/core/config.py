from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables and .env file.
    Pydantic will automatically validate these variables.
    """
    PROJECT_NAME: str = "CareerAI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    FAST_MODEL_NAME: str = "poolside/laguna-xs.2"
    QUALITY_MODEL_NAME: str = "poolside/laguna-m.1"

    # Load configuration from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Instantiate settings to be imported across the application
settings = Settings()
