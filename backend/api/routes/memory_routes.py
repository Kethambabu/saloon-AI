import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

# Project imports
from infrastructure.db import get_db, User, UserRole
from api.deps import get_current_user, RoleChecker
from infrastructure.db.models import CuratedMemory, MemoryScope, MemoryStatus
from application.services.memory_curator_service import MemoryCuratorService
from infrastructure.events.event_bus import SalonEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

# Role checker for admin/manager permissions
check_admin_manager = RoleChecker([UserRole.ADMIN, UserRole.MANAGER])


class ProcessEventRequest(BaseModel):
    event_type: str = Field(..., description="The domain event type, e.g. customer.preference")
    tenant_id: str = Field("default", description="The tenant identifier")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary event payload fields")


class CuratedMemoryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: str
    scope: str
    owner_id: Optional[str] = None
    content: str
    source_event_id: Optional[str] = None
    source_type: Optional[str] = None
    status: str
    confidence: float
    importance: float
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post(
    "/events/process",
    status_code=status.HTTP_200_OK,
    summary="Submit a domain event to the memory curator"
)
async def process_domain_event(
    request: ProcessEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Submit a domain event to the Memory Curator Service.
    It evaluates the event through Layer 1 (policy) and Layer 2 (LLM),
    then saves to SQL and FAISS if deemed durable.
    """
    logger.info(f"[Memory API] Processing event {request.event_type} requested by {current_user.email}")
    try:
        # Construct a generic SalonEvent from request
        event = SalonEvent(
            tenant_id=request.tenant_id,
            event_type=request.event_type,
            payload=request.payload
        )
        curator = MemoryCuratorService()
        result = await curator.process_event(db, event)
        if result:
            return {
                "success": True,
                "stored": True,
                "memory": CuratedMemoryResponse.from_orm(result)
            }
        else:
            return {
                "success": True,
                "stored": False,
                "message": "Event did not trigger long-term memory storage."
            }
    except Exception as e:
        logger.error(f"[Memory API] Failed to process event: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process event: {str(e)}"
        )


@router.get(
    "/curated",
    response_model=List[CuratedMemoryResponse],
    summary="List curated memories"
)
def list_curated_memories(
    scope: Optional[MemoryScope] = Query(None, description="Filter by memory scope"),
    status_filter: Optional[MemoryStatus] = Query(None, alias="status", description="Filter by status"),
    owner_id: Optional[str] = Query(None, description="Filter by owner ID"),
    tenant_id: str = Query("default", description="Filter by tenant ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    List database records of curated memories with optional filters.
    """
    logger.info(f"[Memory API] Curated memory list requested by {current_user.email}")
    query = db.query(CuratedMemory).filter(CuratedMemory.tenant_id == tenant_id)
    if scope:
        query = query.filter(CuratedMemory.scope == scope)
    if status_filter:
        query = query.filter(CuratedMemory.status == status_filter)
    else:
        query = query.filter(CuratedMemory.status == MemoryStatus.ACTIVE)
    if owner_id:
        query = query.filter(CuratedMemory.owner_id == owner_id)
        
    return query.all()


@router.delete(
    "/curated/{memory_id}",
    summary="Forget a curated memory (forget/delete path)"
)
def forget_curated_memory(
    memory_id: uuid.UUID,
    tenant_id: str = Query("default", description="Tenant ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Deletes the memory completely from both SQL metadata and local FAISS vector store.
    """
    logger.info(f"[Memory API] Forget curated memory {memory_id} requested by {current_user.email}")
    curator = MemoryCuratorService()
    success = curator.forget_memory(db, memory_id, tenant_id=tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found or unauthorized tenant."
        )
    return {"success": True, "message": "Memory successfully forgotten and deleted from all indices."}


@router.get(
    "/curated/search",
    summary="Semantic search over curated memories"
)
def search_curated_memories(
    q: str = Query(..., description="Semantic search query"),
    scope: MemoryScope = Query(MemoryScope.CUSTOMER, description="Domain/Scope to search"),
    tenant_id: str = Query("default", description="Tenant ID"),
    owner_id: Optional[str] = Query(None, description="Filter results for a specific owner"),
    k: int = Query(3, description="Number of results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """
    Performs semantic search over curated memories using per-tenant/per-domain FAISS index,
    validating results against SQL to ensure authority.
    """
    logger.info(f"[Memory API] Semantic memory search by {current_user.email} (q='{q}', scope={scope.value})")
    from infrastructure.rag.retriever import search_curated_memory
    
    results = search_curated_memory(
        domain=scope.value,
        query=q,
        tenant_id=tenant_id,
        owner_id=owner_id,
        k=k
    )
    return results


@router.get(
    "/status",
    summary="Get memory system status"
)
def get_memory_status(
    current_user: User = Depends(check_admin_manager)
):
    """
    Get vector index storage configuration status.
    """
    from infrastructure.rag.retriever import get_retriever
    try:
        retriever = get_retriever()
        status_info = retriever.get_status()
        status_info["event_driven_memory"] = {
            "active": True,
            "architecture": "Event-Driven Curated Memory Store (FAISS + SQL)",
            "migration_completed": True
        }
        return status_info
    except Exception as e:
        logger.error(f"[Memory API] Failed to get memory status: {e}")
        return {"success": False, "error": str(e)}


@router.post(
    "/trigger/sync",
    summary="Legacy sync trigger stub"
)
def trigger_legacy_sync(
    current_user: User = Depends(check_admin_manager)
):
    """Legacy endpoint placeholder - returns notice that old sync is retired."""
    return {
        "success": True,
        "action": "skipped",
        "message": "Unified roll-up synchronization is retired. Event-driven memory curation is now active."
    }


@router.post(
    "/trigger/interactions",
    summary="Trigger Customer Interactions RAG Ingestion"
)
def trigger_interactions_ingestion(
    current_user: User = Depends(check_admin_manager)
):
    """
    Rebuild the customer_interactions index from scratch if manually requested.
    """
    logger.info(f"[Memory API] Manual customer interactions RAG trigger requested by {current_user.email}")
    try:
        from infrastructure.rag.ingest import RAGIngestor
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
