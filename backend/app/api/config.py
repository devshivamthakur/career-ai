"""
Configuration and infrastructure classes for Resume Tailor API.
Separated for maintainability and reusability.
"""

import time
import logging
from enum import Enum
from typing import Optional, Dict, Set
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

class ServiceConfig:
    """Centralized performance and resource configuration"""
    
    # Concurrency limits
    MAX_CONCURRENT_REQUESTS = 10
    MAX_CONCURRENT_PDF_PARSING = 5
    
    # Timeouts (seconds)
    JD_VALIDATION_TIMEOUT = 20
    PDF_PARSING_TIMEOUT = 60
    STREAMING_TIMEOUT = 300
    KEEP_ALIVE_TIMEOUT = 15
    
    # Cache configuration
    VALIDATION_CACHE_TTL = 3600  # 1 hour
    JD_HASH_CACHE_SIZE = 100
    
    # Memory optimization
    CHUNK_SIZE = 4096  # bytes
    STREAM_BUFFER_SIZE = 8  # chunks
    
    # File handling
    TEMP_FILE_CLEANUP_DELAY = 60  # seconds
    TEMP_FILE_PREFIX = "resume_tailor_"
    
    # Health monitoring
    ERROR_THRESHOLD = 0.1  # 10% error rate triggers circuit breaker
    ERROR_WINDOW = 60  # seconds


# ═══════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER PATTERN
# ═══════════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Service failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern to handle service degradation gracefully.
    Prevents cascading failures by failing fast when service is struggling.
    """
    
    def __init__(self, failure_threshold: float = 0.5, recovery_timeout: int = 60):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
    
    def record_success(self) -> None:
        """Record successful request"""
        self.failure_count = 0
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker: CLOSED (service recovered)")
    
    def record_failure(self) -> None:
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        failure_rate = self.failure_count / (self.failure_count + self.success_count + 1)
        
        if failure_rate >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker: OPEN (failure threshold exceeded)")
    
    def is_available(self) -> bool:
        """Check if circuit allows requests"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Try recovery after timeout
            if self.last_failure_time and time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: HALF_OPEN (attempting recovery)")
                return True
            return False
        
        return True  # HALF_OPEN allows test request


# ═══════════════════════════════════════════════════════════════════════
# REQUEST CACHING WITH TTL
# ═══════════════════════════════════════════════════════════════════════

class CacheEntry:
    """Cache entry with TTL and metadata"""
    
    def __init__(self, data: any, ttl: int = 3600):
        self.data = data
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = time.time()
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return time.time() - self.created_at > self.ttl
    
    def access(self) -> any:
        """Access data and update metadata"""
        self.last_accessed = time.time()
        self.access_count += 1
        return self.data


class RequestCache:
    """
    LRU-based request cache with TTL support.
    Caches JD validation results and frequently accessed data.
    """
    
    def __init__(self, max_size: int = 100):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[any]:
        """Get value from cache"""
        async with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if not entry.is_expired():
                    return entry.access()
                else:
                    del self.cache[key]
        return None
    
    async def set(self, key: str, value: any, ttl: int = 3600) -> None:
        """Set value in cache with TTL"""
        async with self.lock:
            # Evict oldest entry if cache is full
            if len(self.cache) >= self.max_size:
                oldest_key = min(
                    self.cache.keys(),
                    key=lambda k: self.cache[k].last_accessed
                )
                del self.cache[oldest_key]
            
            self.cache[key] = CacheEntry(value, ttl)
    
    async def clear_expired(self) -> None:
        """Periodic cleanup of expired entries"""
        async with self.lock:
            expired_keys = [
                k for k, v in self.cache.items()
                if v.is_expired()
            ]
            for key in expired_keys:
                del self.cache[key]


# ═══════════════════════════════════════════════════════════════════════
# CONCURRENCY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

class ConcurrencyManager:
    """Manages request concurrency and limits"""
    
    def __init__(self, max_requests: int = 10, max_pdf_tasks: int = 5):
        self.request_semaphore = asyncio.Semaphore(max_requests)
        self.pdf_semaphore = asyncio.Semaphore(max_pdf_tasks)
        self.active_requests: Set[str] = set()
        self.lock = asyncio.Lock()
    
    @asynccontextmanager
    async def request_limit(self, request_id: str):
        """Context manager for request limiting"""
        await self.request_semaphore.acquire()
        async with self.lock:
            self.active_requests.add(request_id)
        
        try:
            yield
        finally:
            async with self.lock:
                self.active_requests.discard(request_id)
            self.request_semaphore.release()
    
    @asynccontextmanager
    async def pdf_limit(self):
        """Context manager for PDF parsing limiting"""
        await self.pdf_semaphore.acquire()
        try:
            yield
        finally:
            self.pdf_semaphore.release()
    
    def get_active_request_count(self) -> int:
        """Get count of active requests"""
        return len(self.active_requests)


# ═══════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCES
# ═══════════════════════════════════════════════════════════════════════

circuit_breaker = CircuitBreaker(
    failure_threshold=ServiceConfig.ERROR_THRESHOLD,
    recovery_timeout=ServiceConfig.ERROR_WINDOW
)

request_cache = RequestCache(max_size=ServiceConfig.JD_HASH_CACHE_SIZE)

concurrency_mgr = ConcurrencyManager(
    max_requests=ServiceConfig.MAX_CONCURRENT_REQUESTS,
    max_pdf_tasks=ServiceConfig.MAX_CONCURRENT_PDF_PARSING
)
