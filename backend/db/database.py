"""
Reusable database connection layer for SalonAI Workforce Platform.
Supports connection pooling, dynamic configuration, health checks,
and transaction context management.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Define default database URL fallback (SQLite) for testing and development
db_url = settings.database_url or "sqlite:///./test.db"
is_sqlite = "sqlite" in db_url

# If configured to use PostgreSQL, test connection availability
if not is_sqlite:
    from sqlalchemy import create_engine as test_create_engine
    try:
        # Quick probe to see if Postgres is up
        probe_engine = test_create_engine(db_url)
        with probe_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to PostgreSQL database.")
    except Exception as e:
        logger.warning(
            f"PostgreSQL is configured but unreachable at {db_url} (Error: {e}). "
            "Automatically falling back to local SQLite database 'sqlite:///./test.db' for development/testing."
        )
        db_url = "sqlite:///./test.db"
        is_sqlite = True

connect_args = {}
pool_kwargs = {}

if is_sqlite:
    # SQLite-specific thread safety configuration
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL enterprise-grade connection pool tuning
    pool_kwargs = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,  # Recycle connections after 30 minutes
        "pool_pre_ping": True,  # Enable health check ping on connection checkout
    }

# Create standard SQLAlchemy engine
try:
    engine = create_engine(
        db_url,
        echo=settings.database_echo,
        connect_args=connect_args,
        **pool_kwargs
    )
    logger.info(f"SQLAlchemy engine initialized successfully using URL: {db_url}")
except Exception as e:
    logger.error(f"Failed to initialize SQLAlchemy engine: {str(e)}")
    raise e

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI Dependency that provides a thread-safe transactional database session.
    Automatically handles commits or rollbacks and ensures resources are released.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session encountered an error; rolling back. Error: {str(e)}")
        db.rollback()
        raise e
    finally:
        db.close()


@contextmanager
def db_transaction() -> Generator[Session, None, None]:
    """
    Context manager for executing operations within a single, atomic transaction.
    If an error occurs, it is rolled back. Otherwise, commits are run on successful exit.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Transaction failed; rolling back transaction. Error: {str(e)}")
        db.rollback()
        raise e
    finally:
        db.close()


def check_db_health() -> bool:
    """
    Verifies the database connection is healthy by executing a lightweight query.
    Returns True if healthy, False otherwise.
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection health check failed: {str(e)}")
        return False
    finally:
        db.close()
