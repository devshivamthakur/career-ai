"""
Shared FastAPI dependencies.

Centralises service singletons, capacity/circuit-breaker pre-flight checks,
and auth/rate-limit wiring so individual routers stay declarative and thin.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from app.agents.career_assistant import CareerAssistantAgent
from app.agents.resume_tailor import ResumeTailorAgent
from app.agents.unified_agent import CareerAgent
from app.core.infrastructure import ServiceConfig, circuit_breaker, concurrency_mgr
from app.services.career_assistant_service import CareerAssistantService
from app.services.resume_tailor_service import ResumeTailorService

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Service singletons (lazy-init, fail-safe)
# ═══════════════════════════════════════════════════════════════════

_career_agent: Optional[CareerAgent] = None
_career_agent_error: Optional[str] = None

_assistant_agent: Optional[CareerAssistantAgent] = None
_assistant_service: Optional[CareerAssistantService] = None
_assistant_error: Optional[str] = None

_resume_agent: Optional[ResumeTailorAgent] = None
_resume_service: Optional[ResumeTailorService] = None
_resume_error: Optional[str] = None


def get_career_agent() -> CareerAgent:
    """Unified chat agent singleton (lazy)."""
    global _career_agent, _career_agent_error
    if _career_agent is None:
        try:
            _career_agent = CareerAgent()
            logger.info("CareerAgent initialized")
        except Exception as exc:  # pragma: no cover - depends on external LLM
            _career_agent_error = str(exc)
            logger.exception("Failed to init CareerAgent: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Career assistant service unavailable",
            )
    return _career_agent


def get_career_assistant_service() -> CareerAssistantService:
    """Cover letter / interview prep service singleton (lazy)."""
    global _assistant_agent, _assistant_service, _assistant_error
    if _assistant_service is None:
        try:
            _assistant_agent = CareerAssistantAgent()
            _assistant_service = CareerAssistantService(_assistant_agent)
            logger.info("CareerAssistantAgent initialized")
        except Exception as exc:  # pragma: no cover - depends on external LLM
            _assistant_error = str(exc)
            logger.exception("Failed to init CareerAssistantAgent: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Career assistant service unavailable",
            )
    return _assistant_service


def get_resume_tailor_service() -> ResumeTailorService:
    """Resume tailor service singleton (lazy)."""
    global _resume_agent, _resume_service, _resume_error
    if _resume_service is None:
        try:
            _resume_agent = ResumeTailorAgent()
            _resume_service = ResumeTailorService(_resume_agent)
            logger.info("ResumeTailorAgent initialized")
        except Exception as exc:  # pragma: no cover - depends on external LLM
            _resume_error = str(exc)
            logger.exception("Failed to init ResumeTailorAgent: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Resume tailoring service unavailable",
            )
    return _resume_service


# ═══════════════════════════════════════════════════════════════════
# Pre-flight checks
# ═══════════════════════════════════════════════════════════════════

async def ensure_capacity() -> None:
    """Reject when the server is at its concurrency limit."""
    active = concurrency_mgr.get_active_request_count()
    if active >= ServiceConfig.MAX_CONCURRENT_REQUESTS:
        logger.warning("Concurrency limit reached (%s)", active)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Server at capacity, please retry in a moment",
        )


async def ensure_circuit_closed() -> None:
    """Reject when the circuit breaker is open."""
    if not circuit_breaker.is_available():
        logger.warning("Circuit breaker open")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service experiencing high failure rate, please retry later",
        )
