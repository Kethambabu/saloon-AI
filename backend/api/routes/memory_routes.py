"""
FastAPI Router for Memory Pipeline Trigger Operations.
Enables administrators and managers to manually consolidate memory databases.
"""

import logging
import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session

# Project imports
from db import get_db, User, UserRole
from api.deps import get_current_user, RoleChecker
from services.memory_pipeline_service import MemoryPipelineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

_memory_service = None


def get_memory_service() -> MemoryPipelineService:
    """Lazily load and cache the MemoryPipelineService singleton."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryPipelineService()
    return _memory_service

# Role checker for admin/manager permissions
check_admin_manager = RoleChecker([UserRole.ADMIN, UserRole.MANAGER])


@router.post(
    "/trigger/daily",
    status_code=status.HTTP_200_OK,
    summary="Trigger daily memory consolidation pipeline"
)
async def trigger_daily_pipeline(
    date_str: Optional[str] = Query(None, description="Target date in YYYY-MM-DD format (defaults to today)"),
    agent_name: Optional[str] = Query(None, description="Target agent memory (receptionist, customer, staff, lead, upsell, reputation, business_intelligence)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Manually run the daily memory pipeline for the specified date.
    Extracts customer queries, staff performance, leads updates, review ratings,
    and upsells from PostgreSQL, compiles them using LLM summaries, and loads them into daily FAISS indices.
    """
    logger.info(f"[Memory API] Manual daily trigger requested by {current_user.email} (date: {date_str or 'today'}, agent: {agent_name or 'all'})")
    
    try:
        if date_str:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = datetime.date.today()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    try:
        memory_service = get_memory_service()
        results = await memory_service.run_daily_pipeline(db, target_date, agent_name=agent_name)
        return {
            "success": True,
            "message": f"Daily memory pipeline processed successfully for {target_date}.",
            "details": results
        }
    except Exception as e:
        logger.error(f"[Memory API] Daily pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Daily memory compilation failed: {str(e)}"
        )


@router.post(
    "/trigger/weekly",
    status_code=status.HTTP_200_OK,
    summary="Trigger weekly memory consolidation pipeline"
)
async def trigger_weekly_pipeline(
    end_date_str: Optional[str] = Query(None, description="End date of the week in YYYY-MM-DD format (defaults to today)"),
    agent_name: Optional[str] = Query(None, description="Target agent memory (receptionist, customer, staff, lead, upsell, reputation, business_intelligence)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Manually compile weekly memories from daily FAISS summaries for the last 7 days.
    Creates weekly summaries for all agents and isolates customer/staff records.
    """
    logger.info(f"[Memory API] Manual weekly trigger requested by {current_user.email} (end_date: {end_date_str or 'today'}, agent: {agent_name or 'all'})")
    
    try:
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = datetime.date.today()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    try:
        memory_service = get_memory_service()
        results = await memory_service.run_weekly_pipeline(db, end_date, agent_name=agent_name)
        return {
            "success": True,
            "message": f"Weekly memory pipeline processed successfully ending {end_date}.",
            "details": results
        }
    except Exception as e:
        logger.error(f"[Memory API] Weekly pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Weekly memory compilation failed: {str(e)}"
        )


@router.post(
    "/trigger/monthly",
    status_code=status.HTTP_200_OK,
    summary="Trigger monthly memory consolidation pipeline"
)
async def trigger_monthly_pipeline(
    end_date_str: Optional[str] = Query(None, description="End date of the month in YYYY-MM-DD format (defaults to today)"),
    agent_name: Optional[str] = Query(None, description="Target agent memory (receptionist, customer, staff, lead, upsell, reputation, business_intelligence)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Manually compile monthly memories from weekly FAISS summaries for the last 30 days.
    """
    logger.info(f"[Memory API] Manual monthly trigger requested by {current_user.email} (end_date: {end_date_str or 'today'}, agent: {agent_name or 'all'})")
    
    try:
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = datetime.date.today()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    try:
        memory_service = get_memory_service()
        results = await memory_service.run_monthly_pipeline(db, end_date, agent_name=agent_name)
        return {
            "success": True,
            "message": f"Monthly memory pipeline processed successfully ending {end_date}.",
            "details": results
        }
    except Exception as e:
        logger.error(f"[Memory API] Monthly pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Monthly memory compilation failed: {str(e)}"
        )


@router.post(
    "/trigger/yearly",
    status_code=status.HTTP_200_OK,
    summary="Trigger yearly memory consolidation pipeline"
)
async def trigger_yearly_pipeline(
    year: Optional[int] = Query(None, description="Target year to compile (defaults to current year)"),
    agent_name: Optional[str] = Query(None, description="Target agent memory (receptionist, customer, staff, lead, upsell, reputation, business_intelligence)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Manually compile yearly memories from monthly FAISS summaries for the specified year.
    """
    logger.info(f"[Memory API] Manual yearly trigger requested by {current_user.email} (year: {year or 'current'}, agent: {agent_name or 'all'})")
    
    if year is None:
        year = datetime.date.today().year

    try:
        memory_service = get_memory_service()
        results = await memory_service.run_yearly_pipeline(db, year, agent_name=agent_name)
        return {
            "success": True,
            "message": f"Yearly memory pipeline processed successfully for year {year}.",
            "details": results
        }
    except Exception as e:
        logger.error(f"[Memory API] Yearly pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Yearly memory compilation failed: {str(e)}"
        )


@router.post(
    "/trigger/interactions",
    status_code=status.HTTP_200_OK,
    summary="Trigger Customer Interactions RAG Ingestion"
)
async def trigger_interactions_ingestion(
    current_user: User = Depends(check_admin_manager)
):
    """
    Manually trigger customer interactions index ingestion.
    Rebuilds the 'customer_interactions' FAISS index from the database contents.
    """
    logger.info(f"[Memory API] Manual customer interactions RAG trigger requested by {current_user.email}")
    try:
        from rag.ingest import RAGIngestor
        ingestor = RAGIngestor()
        results = ingestor.ingest_interactions(force_rebuild=True)
        return {
            "success": True,
            "message": "Customer interactions index ingested successfully.",
            "details": results
        }
    except Exception as e:
        logger.error(f"[Memory API] Interactions ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Customer interactions ingestion failed: {str(e)}"
        )


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get current vector database synchronization status"
)
def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Get synchronization dates boundaries and whether sync is available.
    """
    logger.info(f"[Memory API] Sync status requested by {current_user.email}")
    try:
        service = get_memory_service()
        return service.get_sync_status(db)
    except Exception as e:
        logger.error(f"[Memory API] Failed to get sync status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sync status: {str(e)}"
        )


@router.post(
    "/trigger/sync",
    status_code=status.HTTP_200_OK,
    summary="Trigger unified vector database synchronization"
)
async def trigger_unified_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Triggers unified day-by-day incremental synchronization loop, saving narratives
    to PostgreSQL and rebuilding FAISS indexes once at the end.
    """
    logger.info(f"[Memory API] Unified sync triggered by {current_user.email}")
    service = get_memory_service()
    
    if getattr(service, "is_syncing", False):
        return {
            "success": True,
            "action": "skipped",
            "message": "Vector database synchronization is already in progress in the background."
        }

    try:
        status_info = service.get_sync_status(db)
        if not status_info["sync_available"]:
            return {
                "success": True,
                "action": "skipped",
                "message": "Vector database is already up to date.",
                "details": status_info
            }
    except Exception as e:
        logger.error(f"[Memory API] Failed to check sync status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check synchronization status: {str(e)}"
        )

    async def run_sync_in_background():
        from db.database import SessionLocal
        logger.info("[Memory API] Background task started for unified sync.")
        service.is_syncing = True
        bg_db = SessionLocal()
        try:
            await service.run_unified_sync(bg_db)
        except Exception as bg_err:
            logger.error(f"[Memory API] Background unified sync failed: {bg_err}", exc_info=True)
        finally:
            bg_db.close()
            service.is_syncing = False
            logger.info("[Memory API] Background task completed for unified sync.")

    background_tasks.add_task(run_sync_in_background)
    
    return {
        "success": True,
        "action": "synchronized",
        "message": "Vector database synchronization initiated in the background. Please refresh in a few minutes to see the updated status.",
        "details": {
            "start_date": status_info["next_sync_start"],
            "end_date": status_info["next_sync_end"]
        }
    }
