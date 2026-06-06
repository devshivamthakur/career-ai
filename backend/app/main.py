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


def get_application() -> FastAPI:
    """
    Initialize and configure the FastAPI application.
    Sets up CORS, routers, and basic app metadata.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="API for CareerAI - AI-Powered Job Application & Interview Prep Assistant",
        # Disable OpenAPI docs in production for security
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # Configure CORS for the frontend connection
    # Update allow_origins in production to strictly allow only the frontend domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ENVIRONMENT != "production" else ["https://your-frontend-domain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
