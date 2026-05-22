from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Initialize SQLAlchemy engine
# Use pool_pre_ping to check connection validity before borrowing from the pool
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # Additional production optimizations can go here
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
