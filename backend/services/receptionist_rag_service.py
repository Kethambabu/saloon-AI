import io
import os
import logging
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
    logging.getLogger(__name__).warning("pypdf not installed. PDF upload functionality will be unavailable. Install with: pip install pypdf")
from langchain_core.documents import Document

# Project imports
from db.models import KnowledgeDocument, SpecialOffer
from rag.ingest import DocumentChunker
from rag.embeddings import get_embedding_model

logger = logging.getLogger(__name__)

# Directory path for Receptionist Knowledge Base FAISS
_RECEPTIONIST_KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "faiss_indices",
    "receptionist_knowledge"
)

# Ensure the directory exists
os.makedirs(_RECEPTIONIST_KNOWLEDGE_DIR, exist_ok=True)


class ReceptionistRAGService:
    """
    Manages Salon Receptionist static and promotional knowledge ingestion,
    extracting text from PDFs, saving metadata in database, and rebuilding
    the local FAISS index for agent query matching.
    """

    def __init__(self):
        self.embedding_model = get_embedding_model()
        self.chunker = DocumentChunker(chunk_size=512, chunk_overlap=64)

    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extracts plain text from PDF bytes."""
        if PdfReader is None:
            raise ImportError("pypdf is required for PDF parsing. Install with: pip install pypdf")
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"[ReceptionistRAGService] PDF text extraction failed: {e}")
            raise ValueError(f"Failed to parse PDF document: {str(e)}")

    def upload_policy_document(
        self, db: Session, title: str, doc_type: str, file_bytes: bytes, file_name: str
    ) -> KnowledgeDocument:
        """
        Extract text from file (PDF or TXT), mark older versions inactive,
        save the new KnowledgeDocument in DB, and rebuild FAISS index.
        """
        # 1. Extract text content based on file extension
        ext = file_name.split(".")[-1].lower() if "." in file_name else "txt"
        if ext == "pdf":
            content = self.extract_text_from_pdf(file_bytes)
        else:
            # Assume text/plain or similar
            try:
                content = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = file_bytes.decode("latin-1", errors="ignore")

        if not content.strip():
            raise ValueError("Document is empty or text extraction returned no content.")

        # 2. Deactivate previous active documents of the same type
        db.query(KnowledgeDocument).filter(
            KnowledgeDocument.document_type == doc_type,
            KnowledgeDocument.is_active == True,
            KnowledgeDocument.is_deleted == False
        ).update({"is_active": False})
        db.flush()

        # 3. Determine next version number
        latest_doc = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.document_type == doc_type,
            KnowledgeDocument.is_deleted == False
        ).order_by(KnowledgeDocument.version.desc()).first()
        next_version = (latest_doc.version + 1) if latest_doc else 1

        # 4. Create and save new KnowledgeDocument
        new_doc = KnowledgeDocument(
            title=title,
            document_type=doc_type,
            content=content,
            version=next_version,
            is_active=True,
            is_deleted=False
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        logger.info(f"[ReceptionistRAGService] Uploaded {doc_type} V{next_version} ({new_doc.title})")

        # 5. Rebuild FAISS index
        self.rebuild_receptionist_knowledge_index(db)
        return new_doc

    def delete_policy_document(self, db: Session, doc_id: Any) -> bool:
        """Soft-delete a document, deactivate it, and rebuild the FAISS index."""
        import uuid
        if isinstance(doc_id, str):
            try:
                doc_id = uuid.UUID(doc_id)
            except ValueError:
                pass
        doc = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.is_deleted == False
        ).first()
        if not doc:
            return False

        doc.is_deleted = True
        doc.is_active = False
        db.commit()
        logger.info(f"[ReceptionistRAGService] Soft-deleted document: {doc.title} (ID: {doc_id})")

        # Rebuild FAISS index
        self.rebuild_receptionist_knowledge_index(db)
        return True

    def create_special_offer(
        self, db: Session, title: str, description: str, discount_pct: float, start_date: datetime.date, end_date: datetime.date
    ) -> SpecialOffer:
        """Create a new special offer and rebuild FAISS."""
        new_offer = SpecialOffer(
            title=title,
            description=description,
            discount_pct=discount_pct,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
            is_deleted=False
        )
        db.add(new_offer)
        db.commit()
        db.refresh(new_offer)
        logger.info(f"[ReceptionistRAGService] Created offer: {new_offer.title}")

        # Rebuild FAISS
        self.rebuild_receptionist_knowledge_index(db)
        return new_offer

    def update_special_offer(
        self, db: Session, offer_id: Any, title: Optional[str] = None, description: Optional[str] = None,
        discount_pct: Optional[float] = None, start_date: Optional[datetime.date] = None, end_date: Optional[datetime.date] = None,
        is_active: Optional[bool] = None
    ) -> Optional[SpecialOffer]:
        """Update a special offer and rebuild FAISS."""
        import uuid
        if isinstance(offer_id, str):
            try:
                offer_id = uuid.UUID(offer_id)
            except ValueError:
                pass
        offer = db.query(SpecialOffer).filter(
            SpecialOffer.id == offer_id,
            SpecialOffer.is_deleted == False
        ).first()
        if not offer:
            return None

        if title is not None:
            offer.title = title
        if description is not None:
            offer.description = description
        if discount_pct is not None:
            offer.discount_pct = discount_pct
        if start_date is not None:
            offer.start_date = start_date
        if end_date is not None:
            offer.end_date = end_date
        if is_active is not None:
            offer.is_active = is_active

        db.commit()
        db.refresh(offer)
        logger.info(f"[ReceptionistRAGService] Updated offer: {offer.title}")

        # Rebuild FAISS
        self.rebuild_receptionist_knowledge_index(db)
        return offer

    def delete_special_offer(self, db: Session, offer_id: Any) -> bool:
        """Soft-delete a special offer and rebuild FAISS."""
        import uuid
        if isinstance(offer_id, str):
            try:
                offer_id = uuid.UUID(offer_id)
            except ValueError:
                pass
        offer = db.query(SpecialOffer).filter(
            SpecialOffer.id == offer_id,
            SpecialOffer.is_deleted == False
        ).first()
        if not offer:
            return False

        offer.is_deleted = True
        offer.is_active = False
        db.commit()
        logger.info(f"[ReceptionistRAGService] Soft-deleted offer: {offer.title} (ID: {offer_id})")

        # Rebuild FAISS
        self.rebuild_receptionist_knowledge_index(db)
        return True

    def rebuild_receptionist_knowledge_index(self, db: Session) -> int:
        """
        Loads all active policies and special offers from the database,
        chunks them, embeds them, and replaces the local FAISS index.
        """
        logger.info("[ReceptionistRAGService] Rebuilding local FAISS knowledge index...")
        from langchain_community.vectorstores import FAISS

        langchain_docs = []

        # 1. Load active policy documents
        policies = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.is_active == True,
            KnowledgeDocument.is_deleted == False
        ).all()

        for policy in policies:
            # We chunk the policy text
            chunks = self.chunker.chunk_text(
                policy.content,
                metadata={
                    "type": "policy",
                    "document_type": policy.document_type,
                    "document_id": str(policy.id),
                    "title": policy.title,
                    "version": policy.version
                }
            )
            langchain_docs.extend(chunks)

        # 2. Load active and current special offers
        today = datetime.date.today()
        offers = db.query(SpecialOffer).filter(
            SpecialOffer.is_active == True,
            SpecialOffer.is_deleted == False,
            SpecialOffer.start_date <= today,
            SpecialOffer.end_date >= today
        ).all()

        for offer in offers:
            # Formulate a narrative text block for semantic matching
            offer_narrative = (
                f"Special Offer Details:\n"
                f"Offer Title: {offer.title}\n"
                f"Description: {offer.description}\n"
                f"Discount: {offer.discount_pct}% discount\n"
                f"Validity Period: From {offer.start_date} to {offer.end_date}\n"
                f"Status: Currently active special promotion."
            )
            chunks = self.chunker.chunk_text(
                offer_narrative,
                metadata={
                    "type": "offer",
                    "offer_id": str(offer.id),
                    "title": offer.title,
                    "discount_pct": offer.discount_pct
                }
            )
            langchain_docs.extend(chunks)

        # 3. Handle empty document list (if all policies deleted)
        if not langchain_docs:
            placeholder = Document(
                page_content="No salon policies or offers are currently configured.",
                metadata={"type": "placeholder"}
            )
            langchain_docs.append(placeholder)

        # 4. Re-create and save the FAISS vectorstore
        vectorstore = FAISS.from_documents(langchain_docs, self.embedding_model)
        vectorstore.save_local(_RECEPTIONIST_KNOWLEDGE_DIR)
        logger.info(f"[ReceptionistRAGService] Successfully index rebuilt with {len(langchain_docs)} chunks at {_RECEPTIONIST_KNOWLEDGE_DIR}")
        return len(langchain_docs)

    def deactivate_expired_offers(self, db: Session) -> int:
        """Deactivates expired offers and rebuilds the FAISS index if changes occur."""
        today = datetime.date.today()
        expired_count = db.query(SpecialOffer).filter(
            SpecialOffer.is_active == True,
            SpecialOffer.is_deleted == False,
            SpecialOffer.end_date < today
        ).update({"is_active": False})

        if expired_count > 0:
            db.commit()
            logger.info(f"[ReceptionistRAGService] Deactivated {expired_count} expired offers.")
            self.rebuild_receptionist_knowledge_index(db)
        return expired_count
