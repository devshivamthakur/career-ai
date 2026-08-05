from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Initialize SQLAlchemy engine with production pool settings.
#   - pool_pre_ping: verify the connection before borrowing from the pool
#     (survives DB restarts / dropped connections behind a proxy)
#   - pool_size / max_overflow: bound total connections per worker
#   - pool_recycle: recycle stale connections to avoid TIME_WAIT exhaustion
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    echo=False,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy models
Base = declarative_base()

def get_db():
    """
    Dependency to yield a database session per request.
    Ensures the connection is properly closed after the request is complete.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
