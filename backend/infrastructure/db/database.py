"""
Reusable database connection layer for SalonAI Workforce Platform.
Supports connection pooling, dynamic configuration, health checks,
and transaction context management with production-safe retry logic.

Primary database: Supabase PostgreSQL
Fallback database: Local SQLite (when Supabase is unreachable)
"""

import logging
import time
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import sessionmaker, Session

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

db_url = settings.database_url

# ---------------------------------------------------------------------------
# Fallback SQLite path (used when Supabase is unavailable)
# ---------------------------------------------------------------------------
_SQLITE_FALLBACK_PATH = os.path.join(settings.data_dir, "salon_local.db")
_SQLITE_FALLBACK_URL = f"sqlite:///{os.path.abspath(_SQLITE_FALLBACK_PATH)}"


def _build_engine(url: str):
    """
    Build a SQLAlchemy engine with the appropriate options for the DB type.
    PostgreSQL gets connection pool tuning; SQLite gets simpler settings.
    """
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        # SQLite does not support connection pool kwargs
        engine = create_engine(
            url,
            echo=settings.database_echo,
            connect_args={"check_same_thread": False},
        )
    else:
        # Supabase transaction-mode pooler (port 6543) does NOT support prepared
        # statements when using asyncpg. For psycopg2, this param is not needed.
        if "asyncpg" in url and "pooler.supabase.com" in url and "prepared_statement_cache_size" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}prepared_statement_cache_size=0"

        # PostgreSQL enterprise-grade connection pool tuning for Supabase
        pool_kwargs = {
            "pool_size": 5,        # Reduced for Supabase free tier connection limits
            "max_overflow": 3,     # Reduced to avoid exceeding Supabase connection limits
            "pool_recycle": 1800,  # Recycle connections after 30 minutes
            "pool_pre_ping": True,  # Enable health check ping on connection checkout
        }
        engine = create_engine(
            url,
            echo=settings.database_echo,
            **pool_kwargs,
        )

    return engine


# ---------------------------------------------------------------------------
# Engine creation — try Supabase first, fallback to SQLite
# ---------------------------------------------------------------------------
engine = None
_using_fallback = False

if db_url:
    try:
        logger.info("[DB] Attempting to connect to primary Supabase database...")
        engine = _build_engine(db_url)
        # Eagerly probe the connection to detect unreachable Supabase early
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[DB] ✅ SQLAlchemy engine connected to Supabase successfully.")
    except Exception as e:
        if settings.is_production:
            logger.critical(
                f"[DB] ❌ Supabase connection failed: {e}. "
                "Production environment requires Supabase database. SQLite fallback is disabled."
            )
            raise RuntimeError("Database connection failure. SQLite fallback disabled in production.") from e
        else:
            logger.warning(
                f"[DB] ⚠️  Supabase connection failed: {e}. "
                f"Falling back to local SQLite database at: {_SQLITE_FALLBACK_URL}"
            )
            engine = None

if engine is None:
    if settings.is_production:
        logger.critical("[DB] ❌ Supabase database URL is not configured. SQLite fallback is disabled in production.")
        raise RuntimeError("Supabase database url not configured in production.")
    try:
        # Ensure the local data directory exists
        os.makedirs(os.path.dirname(os.path.abspath(_SQLITE_FALLBACK_PATH)), exist_ok=True)
        engine = _build_engine(_SQLITE_FALLBACK_URL)
        _using_fallback = True
        logger.warning(
            "[DB] 🟡 Running on LOCAL SQLite fallback database. "
            "Data will NOT be synced to Supabase until connection is restored."
        )
    except Exception as fallback_err:
        logger.critical(f"[DB] ❌ SQLite fallback failed: {fallback_err}")
        raise RuntimeError(
            "Could not initialise any database connection. "
            "Check DATABASE_URL in .env and ensure the data/ directory is writable."
        ) from fallback_err



# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def is_using_fallback() -> bool:
    """Returns True if the app is currently using the SQLite fallback."""
    return _using_fallback


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI Dependency that provides a thread-safe transactional database session.
    Automatically handles commits or rollbacks and ensures resources are released.
    """
    db = SessionLocal()
    try:
        yield db
    except StarletteHTTPException as e:
        # Starlette / FastAPI HTTPExceptions are normal API flows (e.g. 401, 403, 404).
        # We roll back the session to be safe, but do not log this as a DB error.
        db.rollback()
        raise e
    except Exception as e:
        logger.error(f"Database session encountered an error; rolling back. Error: {str(e)}", exc_info=True)
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
    except StarletteHTTPException as e:
        # Rollback the transaction on HTTP exception, but do not log it as a DB error.
        db.rollback()
        raise e
    except Exception as e:
        logger.error(f"Transaction failed; rolling back transaction. Error: {str(e)}", exc_info=True)
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

