"""Database module with SQLAlchemy ORM setup"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from core.config import get_settings

settings = get_settings()

# Database setup
engine = create_engine(
    settings.database_url or "sqlite:///./test.db",
    echo=settings.database_echo,
    connect_args={"check_same_thread": False} if "sqlite" in (settings.database_url or "") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Session:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["engine", "SessionLocal", "Base", "get_db"]
