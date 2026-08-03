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

    # Connection pool tuning (per gunicorn worker)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800   # recycle connections every 30 min
    DB_POOL_TIMEOUT: int = 30     # seconds to wait for a free connection

    # Redis Cache
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379"

    @property
    def resolved_redis_url(self) -> str:
        """Return the effective Redis URL, using REDIS_HOST if provided."""
        if self.REDIS_HOST:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"
        return self.REDIS_URL
    
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
    # TOKEN & COST LIMITS
    # ═════════════════════════════════════════════════════════════

    # Max output tokens per LLM response
    FAST_MODEL_MAX_TOKENS: int = 4096
    QUALITY_MODEL_MAX_TOKENS: int = 8192
    AGENT_MAX_TOKENS: int = 4096       # Max tokens for agent-style responses
    AGENT_RECURSION_LIMIT: int = 100   # Max LangGraph recursion steps (tool calls + LLM rounds)
    COVER_LETTER_MAX_TOKENS: int = 2048
    INTERVIEW_PREP_MAX_TOKENS: int = 4096

    # Max context window safety limit (total input + output)
    # Prevents runaway token usage on models with large context
    MAX_CONTEXT_TOKENS: int = 32000

    # Token budget per conversation thread (for cost control)
    THREAD_TOKEN_BUDGET: int = 64000   # Hard ceiling per session

    # ═════════════════════════════════════════════════════════════
    # SECURITY & CORS CONFIGURATION
    # ═════════════════════════════════════════════════════════════
    
    # CORS - Allowed origins for frontend access
    # In production, set to your actual frontend domain
    # Example: "https://example.com" or comma-separated list
    ALLOWED_ORIGINS: str = ""
    
    # Security - Hide OpenAPI/Swagger docs in production
    HIDE_DOCS_IN_PRODUCTION: bool = False
    
    # Security - Enable/disable various security headers
    ENABLE_SECURITY_HEADERS: bool = True
    
    # API Key for additional authentication (optional)
    API_KEY: Optional[str] = None

    # Allowed Host headers (TrustedHostMiddleware). Comma-separated; "*" allows all.
    ALLOWED_HOSTS: str = "*"

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Parse ALLOWED_HOSTS into a list. "*" means allow all hosts."""
        if self.ALLOWED_HOSTS.strip() == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    # Maximum accepted request body size (MB) — guards against abuse
    MAX_BODY_SIZE_MB: int = 15
    
    # Emit an access-log line per request (structured, request-id correlated)
    ENABLE_REQUEST_LOGGING: bool = True
    
    # CORS detailed configuration
    ALLOW_CREDENTIALS: bool = True
    ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    ALLOW_HEADERS: list[str] = ["Content-Type", "Authorization", "X-Request-ID", "X-API-Key"]
    
    # Load configuration from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Instantiate settings to be imported across the application
settings = Settings()
