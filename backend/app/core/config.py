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
    LLM_PROVIDER: str = "openai"
    AWS_REGION: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_CREDENTIALS_PROFILE_NAME: Optional[str] = None
    AWS_MODEL_PROVIDER: str = "mistral"
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_BASE_URL: Optional[str] = None
    HUGGINGFACE_API_TOKEN: Optional[str] = None
    
    FAST_MODEL_NAME: str = "poolside/laguna-xs.2"
    QUALITY_MODEL_NAME: str = "poolside/laguna-m.1"
    EMBEDDING_MODEL_REPO_ID: str = "BAAI/bge-base-en-v1.5"

    # ═════════════════════════════════════════════════════════════
    # SECURITY & CORS CONFIGURATION
    # ═════════════════════════════════════════════════════════════
    
    # CORS - Allowed origins for frontend access
    # In production, set to your actual frontend domain
    # Example: "https://example.com" or comma-separated list
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # Security - Hide Swagger/OpenAPI docs in production
    HIDE_DOCS_IN_PRODUCTION: bool = True
    
    # Security - Enable/disable various security headers
    ENABLE_SECURITY_HEADERS: bool = True
    
    # API Key for additional authentication (optional)
    API_KEY: Optional[str] = None
    
    # CORS detailed configuration
    ALLOW_CREDENTIALS: bool = True
    ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    ALLOW_HEADERS: list[str] = ["Content-Type", "Authorization", "X-Request-ID"]
    
    # Load configuration from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Instantiate settings to be imported across the application
settings = Settings()
