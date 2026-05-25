import logging
import sys

# Basic logging configuration to stream to stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

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

    # Include API routers here
    from app.api.routes import api_router
    from app.api.resume_routes import router as resume_router
    app.include_router(api_router, prefix="/api")
    app.include_router(resume_router)

    return app

app = get_application()

@app.get("/health")
async def health_check():
    """
    Basic health check endpoint to verify the API is running.
    Useful for uptime monitors and Kubernetes liveness probes.
    """
    return {"status": "healthy", "environment": settings.ENVIRONMENT, "version": settings.VERSION}
