from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create engine with connection parameters
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQLALCHEMY_ECHO,
    pool_size=settings.SQLALCHEMY_POOL_SIZE,
    pool_timeout=settings.SQLALCHEMY_POOL_TIMEOUT
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Make the engine available for reflection in models that need it
# This is particularly useful for models that map to existing tables
# managed by other services
Base.metadata.bind = engine

def get_db():
    """
    Get a database session.
    Note: This service only manages the Log model.
    All other models are used for reference but are managed by other services.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()