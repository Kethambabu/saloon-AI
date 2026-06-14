"""
Supabase Service — Establishes and manages the Supabase Python client.

Phase 1: Connection-only.  No data is migrated away from SQLAlchemy yet.
The Supabase client is provided as a singleton for future Phase 2 usage
where individual SalonMCP methods will be progressively migrated.

Environment variables required (already present in .env):
    SUPABASE_URL                — Project REST API URL
    SUPABASE_SERVICE_ROLE_KEY   — Service role key (bypasses RLS; server-side only)
    SUPABASE_ANON_KEY           — Anon key (for public/client-side operations)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection factory (lazy singleton)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_supabase_client():
    """
    Return a cached Supabase client instance (service role).

    Uses the service role key so the server can bypass Row-Level Security
    when performing admin-level MCP operations.

    Returns None (with a warning) if credentials are not configured, so that
    the rest of the application degrades gracefully.
    """
    try:
        from supabase import create_client, Client
        from core.config import get_settings

        settings = get_settings()

        url: Optional[str] = settings.supabase_url
        key: Optional[str] = settings.supabase_service_role_key or settings.supabase_anon_key

        if not url or not key:
            logger.warning(
                "[SupabaseService] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set. "
                "Supabase client will not be available. "
                "Set these in your .env file to enable Phase 2 migration."
            )
            return None

        client: Client = create_client(url, key)
        logger.info(
            "[SupabaseService] ✅ Supabase client initialised successfully. URL: %s",
            url[:40] + "..."
        )
        return client

    except ImportError:
        logger.error(
            "[SupabaseService] ❌ 'supabase' package not installed. "
            "Run: pip install supabase"
        )
        return None
    except Exception as exc:
        logger.error(
            "[SupabaseService] ❌ Failed to initialise Supabase client: %s", exc, exc_info=True
        )
        return None


@lru_cache(maxsize=1)
def get_supabase_anon_client():
    """
    Return a cached Supabase anon client.

    Used for public-facing operations that should respect Row-Level Security.
    """
    try:
        from supabase import create_client, Client
        from core.config import get_settings

        settings = get_settings()
        url: Optional[str] = settings.supabase_url
        key: Optional[str] = settings.supabase_anon_key

        if not url or not key:
            logger.warning(
                "[SupabaseService] SUPABASE_URL or SUPABASE_ANON_KEY not set. "
                "Anon client unavailable."
            )
            return None

        client: Client = create_client(url, key)
        logger.info("[SupabaseService] ✅ Supabase anon client initialised.")
        return client

    except ImportError:
        logger.error("[SupabaseService] ❌ 'supabase' package not installed.")
        return None
    except Exception as exc:
        logger.error("[SupabaseService] ❌ Failed to initialise anon client: %s", exc, exc_info=True)
        return None


def check_supabase_health() -> dict:
    """
    Verify that the Supabase client is reachable.

    Returns a status dict suitable for health-check endpoints.
    """
    client = get_supabase_client()
    if client is None:
        return {"status": "unavailable", "error": "Client not initialised (missing credentials or package)"}

    try:
        # A lightweight probe — list up to 1 row from branches table
        response = client.table("branches").select("id").limit(1).execute()
        return {
            "status": "healthy",
            "rows_probed": len(response.data) if response.data else 0,
        }
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


# ---------------------------------------------------------------------------
# Convenience accessor (module-level)
# ---------------------------------------------------------------------------

#: Module-level access to the service role client.
#: Call get_supabase_client() directly for lazy initialisation.
supabase = None  # Populated on first import via _init_module below


def _init_module():
    """Called once at import time to eagerly attempt client creation."""
    global supabase
    supabase = get_supabase_client()


_init_module()
