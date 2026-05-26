"""Core configuration and utilities for SalonAI Workforce backend."""

from .config import settings
from .logging import setup_logging

__all__ = ["settings", "setup_logging"]
