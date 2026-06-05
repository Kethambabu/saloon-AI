"""
Reusable database connection layer for SalonAI Workforce Platform.
Supports connection pooling, dynamic configuration, health checks,
and transaction context management with production-safe retry logic.
"""

import logging
import time
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

db_url = settings.database_url

if not db_url:
    raise ValueError("DATABASE_URL setting is missing! Supabase connection URL must be specified.")

# Supabase transaction-mode pooler (port 6543) does NOT support prepared statements when using asyncpg.
# For psycopg2 (default postgresql://), prepared_statement_cache_size is not supported and not needed.
if "asyncpg" in db_url and "pooler.supabase.com" in db_url and "prepared_statement_cache_size" not in db_url:
    separator = "&" if "?" in db_url else "?"
    db_url = f"{db_url}{separator}prepared_statement_cache_size=0"

# PostgreSQL enterprise-grade connection pool tuning tailored for Supabase
# Supabase connections can occasionally drop, hence pool_pre_ping and recycle are vital.
pool_kwargs = {
    "pool_size": 5,        # Reduced for Supabase free tier connection limits
    "max_overflow": 3,     # Reduced to avoid exceeding Supabase connection limits
    "pool_recycle": 1800,  # Recycle connections after 30 minutes
    "pool_pre_ping": True,  # Enable health check ping on connection checkout
}

# Create standard SQLAlchemy engine (no network connections are made yet)
try:
    engine = create_engine(
        db_url,
        echo=settings.database_echo,
        **pool_kwargs
    )
    logger.info("SQLAlchemy engine initialized successfully.")
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
    Supports connection retries with exponential backoff on startup.
    Returns True if healthy, False otherwise.
    """
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(1, max_retries + 1):
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db.close()
            return True
        except Exception as e:
            logger.warning(f"Database connection health check attempt {attempt} failed: {str(e)}")
            db.close()
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
                
    logger.error("Database connection health check failed after maximum retries.")
    return False
