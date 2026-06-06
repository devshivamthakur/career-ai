import logging
import sys

# Basic logging configuration to stream to stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
 
from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.rate_limit import rate_limit_dependency
from app.api.services import generate_request_id
from app.core.config import settings
from app.core.caching import initialize_semantic_cache

# Initialize the semantic cache
initialize_semantic_cache()


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = _get_request_id(request)
    logger.warning("Request %s: request validation failed: %s", request_id, exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "request_id": request_id},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = _get_request_id(request)
    logger.warning("Request %s: HTTP exception: %s", request_id, exc.detail)
    content = {"detail": exc.detail, "request_id": request_id}
    if exc.headers:
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content=content)


async def unexpected_exception_handler(request: Request, exc: Exception):
    request_id = _get_request_id(request)
    logger.exception("Request %s: unhandled exception: %s", request_id, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "request_id": request_id},
    )


def _parse_allowed_origins() -> list[str]:
    """Parse ALLOWED_ORIGINS from settings string"""
    if settings.ENVIRONMENT == "production":
        # In production, parse comma-separated origins
        origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
        # Remove any empty strings
        origins = [origin for origin in origins if origin]
        if not origins:
            logger.warning("No allowed origins configured for production")
            origins = []
    else:
        # In development, allow localhost variants
        origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
    
    logger.info("Configured CORS origins: %s", origins)
    return origins


def _add_security_headers_middleware(app: FastAPI) -> None:
    """Add security headers to all responses"""
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        
        if settings.ENABLE_SECURITY_HEADERS:
            # Prevent clickjacking
            response.headers["X-Frame-Options"] = "DENY"
            
            # Prevent MIME type sniffing
            response.headers["X-Content-Type-Options"] = "nosniff"
            
            # Enable XSS protection
            response.headers["X-XSS-Protection"] = "1; mode=block"
            
            # Enforce HTTPS in production
            if settings.ENVIRONMENT == "production":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
            # Content Security Policy
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
            
            # Prevent information leakage
            response.headers["X-Powered-By"] = ""
            if "Server" in response.headers:
                del response.headers["Server"]
        
        return response


def get_application() -> FastAPI:
    """
    Initialize and configure the FastAPI application.
    Sets up CORS, security headers, routers, and basic app metadata.
    """
    # Determine if docs should be visible
    is_production = settings.ENVIRONMENT == "production"
    show_docs = not (is_production and settings.HIDE_DOCS_IN_PRODUCTION)
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="API for CareerAI - AI-Powered Job Application & Interview Prep Assistant",
        # Hide OpenAPI docs in production for security
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
    )

    # ═══════════════════════════════════════════════════════════════
    # SECURITY: CORS Middleware
    # ═══════════════════════════════════════════════════════════════
    allowed_origins = _parse_allowed_origins()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=settings.ALLOW_CREDENTIALS,
        allow_methods=settings.ALLOW_METHODS,
        allow_headers=settings.ALLOW_HEADERS,
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    # ═══════════════════════════════════════════════════════════════
    # SECURITY: Add Security Headers
    # ═══════════════════════════════════════════════════════════════
    _add_security_headers_middleware(app)

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)

    # Include API routers here
    from app.api.routes import api_router
    from app.api.resume_routes import router as resume_router
    from app.api.assistant_routes import router as assistant_router
    app.include_router(api_router, prefix="/api")
    app.include_router(resume_router, dependencies=[Depends(rate_limit_dependency)])
    app.include_router(assistant_router, dependencies=[Depends(rate_limit_dependency)])

    return app

app = get_application()

@app.get("/health")
async def health_check():
    """
    Basic health check endpoint to verify the API is running.
    Useful for uptime monitors and Kubernetes liveness probes.
    """
    return {"status": "healthy", "environment": settings.ENVIRONMENT, "version": settings.VERSION}
