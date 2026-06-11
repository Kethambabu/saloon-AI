import logging
import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# Project imports
from db import get_db, User, UserRole
from api.deps import get_current_user, RoleChecker
from services.receptionist_rag_service import ReceptionistRAGService
from db.models import KnowledgeDocument, SpecialOffer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin RAG Knowledge Base"])

_rag_service = None

def get_rag_service() -> ReceptionistRAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = ReceptionistRAGService()
    return _rag_service

# Restrict to Admin and Manager roles
check_admin_manager = RoleChecker([UserRole.ADMIN, UserRole.MANAGER])

# Whitelisted document types
ALLOWED_DOC_TYPES = {
    "timings": "Business Timings & Hours Policy",
    "cancellation_policy": "Cancellation & Rescheduling Policy",
    "refund_policy": "Refund & Payment Policy",
    "faq": "Frequently Asked Questions",
    "salon_info": "General Salon Information"
}

# --- Pydantic Schema Models ---

class OfferCreate(BaseModel):
    title: str = Field(..., example="Hair Spa Combo")
    description: str = Field(..., example="Deep-cleansing hair spa plus precision haircut at 30% off.")
    discount_pct: float = Field(default=0.0, ge=0.0, le=100.0, example=30.0)
    start_date: datetime.date = Field(..., example="2026-06-01")
    end_date: datetime.date = Field(..., example="2026-06-30")


class OfferUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    discount_pct: Optional[float] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    is_active: Optional[bool] = None


# --- API Routes ---

@router.post(
    "/knowledge/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload policy or FAQ document"
)
async def upload_knowledge_document(
    title: str = Form(..., description="Descriptive title of the document"),
    document_type: str = Form(..., description="Whitelisted document type: 'timings', 'cancellation_policy', 'refund_policy', 'faq', 'salon_info'"),
    file: UploadFile = File(..., description="PDF or text file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager),
    service: ReceptionistRAGService = Depends(get_rag_service)
):
    """
    Upload a policy document or FAQ list to the Receptionist RAG database.
    Older active versions of the same document type will automatically be deactivated.
    """
    if document_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type. Allowed types: {', '.join(ALLOWED_DOC_TYPES.keys())}"
        )

    # Read file contents (limit to 10MB)
    MAX_SIZE = 10 * 1024 * 1024
    content_bytes = await file.read()
    if len(content_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 10MB limit."
        )

    try:
        doc = service.upload_policy_document(
            db=db,
            title=title,
            doc_type=document_type,
            file_bytes=content_bytes,
            file_name=file.filename
        )
        return {
            "success": True,
            "message": f"Successfully uploaded and indexed V{doc.version} of {document_type}.",
            "document": {
                "id": str(doc.id),
                "title": doc.title,
                "document_type": doc.document_type,
                "version": doc.version,
                "is_active": doc.is_active,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
        }
    except Exception as e:
        logger.error(f"Error in knowledge upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process and index document: {str(e)}"
        )


@router.get(
    "/knowledge/documents",
    summary="List all knowledge base documents"
)
async def list_knowledge_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """List all knowledge documents that have not been permanently deleted."""
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.is_deleted == False
    ).order_by(KnowledgeDocument.document_type, KnowledgeDocument.version.desc()).all()

    return {
        "success": True,
        "documents": [
            {
                "id": str(d.id),
                "title": d.title,
                "document_type": d.document_type,
                "version": d.version,
                "is_active": d.is_active,
                "created_at": d.created_at.isoformat() if d.created_at else None
            }
            for d in docs
        ]
    }


@router.delete(
    "/knowledge/documents/{doc_id}",
    summary="Deactivate and soft-delete a document"
)
async def delete_knowledge_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager),
    service: ReceptionistRAGService = Depends(get_rag_service)
):
    """Mark a document as deleted and rebuild the FAISS knowledge index."""
    success = service.delete_policy_document(db, doc_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or already deleted."
        )
    return {"success": True, "message": "Document successfully deleted and index rebuilt."}


@router.post(
    "/offers",
    status_code=status.HTTP_201_CREATED,
    summary="Create a special promotion offer"
)
async def create_offer(
    offer_data: OfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager),
    service: ReceptionistRAGService = Depends(get_rag_service)
):
    """Create a special offer and index its details into the local FAISS knowledge base."""
    if offer_data.start_date > offer_data.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date."
        )

    try:
        offer = service.create_special_offer(
            db=db,
            title=offer_data.title,
            description=offer_data.description,
            discount_pct=offer_data.discount_pct,
            start_date=offer_data.start_date,
            end_date=offer_data.end_date
        )
        return {
            "success": True,
            "offer": {
                "id": str(offer.id),
                "title": offer.title,
                "description": offer.description,
                "discount_pct": offer.discount_pct,
                "start_date": offer.start_date.isoformat(),
                "end_date": offer.end_date.isoformat(),
                "is_active": offer.is_active
            }
        }
    except Exception as e:
        logger.error(f"Error creating special offer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create and index special offer: {str(e)}"
        )


@router.get(
    "/offers",
    summary="List special offers"
)
async def list_offers(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager)
):
    """List all configured special offers."""
    offers = db.query(SpecialOffer).filter(SpecialOffer.is_deleted == False).all()
    return {
        "success": True,
        "offers": [
            {
                "id": str(o.id),
                "title": o.title,
                "description": o.description,
                "discount_pct": o.discount_pct,
                "start_date": o.start_date.isoformat(),
                "end_date": o.end_date.isoformat(),
                "is_active": o.is_active
            }
            for o in offers
        ]
    }


@router.put(
    "/offers/{offer_id}",
    summary="Update a special offer"
)
async def update_offer(
    offer_id: str,
    offer_data: OfferUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager),
    service: ReceptionistRAGService = Depends(get_rag_service)
):
    """Update a special offer's details and rebuild the FAISS knowledge index."""
    offer = service.update_special_offer(
        db=db,
        offer_id=offer_id,
        title=offer_data.title,
        description=offer_data.description,
        discount_pct=offer_data.discount_pct,
        start_date=offer_data.start_date,
        end_date=offer_data.end_date,
        is_active=offer_data.is_active
    )
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special offer not found or already deleted."
        )
    return {
        "success": True,
        "offer": {
            "id": str(offer.id),
            "title": offer.title,
            "description": offer.description,
            "discount_pct": offer.discount_pct,
            "start_date": offer.start_date.isoformat(),
            "end_date": offer.end_date.isoformat(),
            "is_active": offer.is_active
        }
    }


@router.delete(
    "/offers/{offer_id}",
    summary="Soft-delete a special offer"
)
async def delete_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager),
    service: ReceptionistRAGService = Depends(get_rag_service)
):
    """Soft-delete an offer and rebuild the FAISS index."""
    success = service.delete_special_offer(db, offer_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special offer not found or already deleted."
        )
    return {"success": True, "message": "Special offer successfully deleted."}


@router.post(
    "/knowledge/rebuild",
    status_code=status.HTTP_200_OK,
    summary="Rebuild Receptionist Knowledge RAG Index"
)
async def rebuild_knowledge_index(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_manager),
    service: ReceptionistRAGService = Depends(get_rag_service)
):
    """
    Manually rebuild the receptionist knowledge base FAISS index from documents and offers in the database.
    """
    logger.info(f"[Admin RAG API] Manual receptionist knowledge RAG rebuild requested by {current_user.email}")
    try:
        chunks_count = service.rebuild_receptionist_knowledge_index(db)
        return {
            "success": True,
            "message": "Receptionist knowledge index rebuilt successfully.",
            "details": {
                "index_name": "receptionist_knowledge",
                "chunks_indexed": chunks_count
            }
        }
    except Exception as e:
        logger.error(f"[Admin RAG API] Receptionist knowledge rebuild failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Receptionist knowledge index rebuild failed: {str(e)}"
        )

