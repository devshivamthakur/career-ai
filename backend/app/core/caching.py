"""
Semantic Caching Configuration
Initializes and configures the Redis-based semantic cache for LLM calls.
"""
import logging
import langchain
from typing import Optional, List, Any
from langchain_core.caches import BaseCache
from app.core.config import settings
from langchain_core.outputs import Generation
import asyncio

logger = logging.getLogger(__name__)

cacheInstance: Optional[BaseCache] = None
class SemanticCacheService():
    """
    A service wrapper for LangChain's RedisSemanticCache to provide explicit
    async methods for lookup, update, and clear, and to act as the global
    LLM cache.
    """

    def __init__(self, redis_cache):
        self._cache = redis_cache
        logger.info("SemanticCacheService initialized.")

    def lookup(self, prompt: str, llm_string: str):
        """Sync lookup is not supported by the underlying Redis cache."""
        logger.warning("Attempted to use sync lookup on an async-only cache.")
        return None

    async def alookup(self, prompt: str, llm_string: str):
        """Async lookup of a prompt in the semantic cache."""
        logger.debug(f"Performing semantic cache lookup for llm_string: {llm_string}")
        return await self._cache.alookup(prompt, llm_string)

    def update(self, prompt: str, llm_string: str, return_val: List[Generation]) -> None:
        """Sync update is not supported by the underlying Redis cache."""
        logger.warning("Attempted to use sync update on an async-only cache.")
        pass

    async def aupdate(self, prompt: str, llm_string: str, return_val: List[Generation]) -> None:
        """Async update of the semantic cache with a new value."""
        logger.debug(f"Updating semantic cache for llm_string: {llm_string}")
        _ = asyncio.create_task(self._cache.aupdate(prompt, llm_string, return_val))

    def clear(self, **kwargs: Any) -> None:
        """Sync clear is not supported."""
        logger.warning("Attempted to use sync clear on an async-only cache.")
        pass

    async def aclear(self, **kwargs: Any) -> None:
        """Async clear the entire cache."""
        logger.info("Clearing semantic cache.")
        await self._cache.aclear(**kwargs)

def get_cache() -> Optional[SemanticCacheService]:
    """Get the initialized cache instance."""
    return cacheInstance

def initialize_semantic_cache():
    """
    Initializes the RedisSemanticCache with a HuggingFace embedding model
    and sets the SemanticCacheService as the global LLM cache for LangChain.
    """
    global cacheInstance
    if not settings.HUGGINGFACE_API_TOKEN:
        logger.warning("HUGGINGFACE_API_TOKEN not found in environment. Skipping semantic cache initialization.")
        return

    try:
        from langchain_huggingface import HuggingFaceEndpointEmbeddings
        from langchain_redis import RedisSemanticCache

        logger.info("Initializing Redis semantic cache service...")

        # Initialize the embedding model from a HuggingFace endpoint
        embeddings = HuggingFaceEndpointEmbeddings(
            repo_id=settings.EMBEDDING_MODEL_REPO_ID,
            huggingfacehub_api_token=settings.HUGGINGFACE_API_TOKEN,
        )

        # Initialize the underlying Redis semantic cache
        redis_cache = RedisSemanticCache(
            redis_url=settings.REDIS_URL,
            embeddings=embeddings,
            distance_threshold=0.7, # Lower threshold for broader matching
            ttl=60 * 60 * 8, # Cache entries expire after 8 hours
        )

        # Set our service as the global LLM cache and the exported instance
        cacheInstance = SemanticCacheService(redis_cache)
        
        logger.info(f"Redis semantic cache service initialized successfully with model: {settings.EMBEDDING_MODEL_REPO_ID}")

    except ImportError as e:
        logger.warning(
            f"Required packages for Redis semantic cache not found: {e}. "
            "Skipping cache initialization. "
            "Please install langchain-redis and langchain-huggingface."
        )
    except Exception as e:
        logger.error(f"Failed to initialize Redis semantic cache: {e}", exc_info=True)

