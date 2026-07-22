"""
Core package for SalonAI Workforce backend.

Phase 1 symbols (config, logging, security) are imported eagerly for
backward compatibility.

Phase 2 symbols (event_bus, capability_registry, workflow_registry,
tenant_context, token_optimizer) are imported lazily via __getattr__
so that the core package can be loaded without pydantic/jose being
present in test/CI environments.
"""

# Phase 2 lazy imports — only loaded when accessed
_PHASE2_MODULES = {
    "event_bus":           "core.event_bus",
    "capability_registry": "core.capability_registry",
    "workflow_registry":   "core.workflow_registry",
    "tenant_context":      "core.tenant_context",
    "token_optimizer":     "core.token_optimizer",
}


def __getattr__(name: str):
    """Lazy-load Phase 2 core modules on first attribute access."""
    if name in _PHASE2_MODULES:
        import importlib
        mod = importlib.import_module(_PHASE2_MODULES[name])
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'core' has no attribute '{name}'")


# Phase 1 eager imports (kept for backward compatibility)
try:
    from .config import Settings, get_settings
    from .logging import setup_logging, get_logger
    from .security import (
        hash_password,
        verify_password,
        create_access_token,
        create_refresh_token,
        decode_token,
    )
except Exception:
    # Graceful fallback when pydantic/jose not installed (test/lint environments)
    pass

__all__ = [
    # Phase 1
    "Settings",
    "get_settings",
    "setup_logging",
    "get_logger",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    # Phase 2
    "event_bus",
    "capability_registry",
    "workflow_registry",
    "tenant_context",
    "token_optimizer",
]

