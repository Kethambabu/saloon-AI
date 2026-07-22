import logging
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from infrastructure.rag.embeddings import get_embedding_model
from core.openai_client_adapter import OpenAIChatCompletionClient

logger = logging.getLogger(__name__)
_DEFAULT_INDEX_DIR = ""

class DeprecatedError(NotImplementedError):
    """Raised when deprecated multi-agent roll-up memory pipeline methods are called."""
    pass


class MemoryPipelineService:
    """
    DEPRECATED: Old hierarchical memory pipeline (daily -> weekly -> monthly -> yearly).
    Replaced by event-driven MemoryCuratorService.
    """

    def __init__(self):
        logger.warning("[MemoryPipelineService] WARNING: This service is deprecated and replaced by MemoryCuratorService.")

    async def run_daily_pipeline(self, db: Session, target_date: Optional[datetime.date] = None, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        raise DeprecatedError("run_daily_pipeline is deprecated. Use event-driven memory curation instead.")

    async def run_weekly_pipeline(self, db: Session, end_date: datetime.date, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        raise DeprecatedError("run_weekly_pipeline is deprecated. Use event-driven memory curation instead.")

    async def run_monthly_pipeline(self, db: Session, end_date: datetime.date, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        raise DeprecatedError("run_monthly_pipeline is deprecated. Use event-driven memory curation instead.")

    async def run_yearly_pipeline(self, db: Session, year: int, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        raise DeprecatedError("run_yearly_pipeline is deprecated. Use event-driven memory curation instead.")

    def get_sync_status(self, db: Session) -> Dict[str, Any]:
        return {
            "deprecated": True,
            "message": "The old memory pipeline is deprecated. Event-driven memory curation is now active.",
            "sync_available": False,
            "next_sync_start": None,
            "next_sync_end": None
        }

    async def run_unified_sync(self, db: Session) -> None:
        raise DeprecatedError("run_unified_sync is deprecated. Use event-driven memory curation instead.")
