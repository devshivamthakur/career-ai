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

    # Rate limiting
    MAX_REQUESTS_PER_CLIENT = 20
    RATE_LIMIT_WINDOW = 60
    
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


concurrency_mgr = ConcurrencyManager(
    max_requests=ServiceConfig.MAX_CONCURRENT_REQUESTS,
    max_pdf_tasks=ServiceConfig.MAX_CONCURRENT_PDF_PARSING
)
