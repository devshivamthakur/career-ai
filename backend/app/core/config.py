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

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379"
    
    # API Keys & Models
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_BASE_URL: Optional[str] = None
    HUGGINGFACE_API_TOKEN: Optional[str] = None
    
    FAST_MODEL_NAME: str = "poolside/laguna-xs.2"
    QUALITY_MODEL_NAME: str = "poolside/laguna-m.1"
    EMBEDDING_MODEL_REPO_ID: str = "BAAI/bge-base-en-v1.5"

    # Load configuration from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Instantiate settings to be imported across the application
settings = Settings()
