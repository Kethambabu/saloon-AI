"""
Document Ingestion Pipeline for SalonAI Workforce RAG System.

Handles loading, chunking, embedding, and indexing of two primary knowledge sources:

    1. **Customer Interaction History** — Pulls conversations, appointments, reviews,
       and lead interactions from the PostgreSQL database and indexes them for
       contextual agent retrieval.

    2. **Salon Knowledge Base** — Ingests static business knowledge (services, policies,
       FAQs, branch info) into a persistent FAISS vector store for semantic search.

Architecture:
    DocumentChunker     →  Splits raw text into overlapping chunks with metadata
    SalonKnowledgeBase  →  Builds and manages the static knowledge FAISS index
    InteractionIndexer  →  Indexes dynamic customer interactions from PostgreSQL
    RAGIngestor         →  Unified facade that orchestrates full ingestion pipelines
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import get_settings
from rag.embeddings import get_embedding_model, EmbeddingConfig

logger = logging.getLogger(__name__)
settings = get_settings()

# Default persistence directory for FAISS indices
_DEFAULT_INDEX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "faiss_indices",
)


# ---------------------------------------------------------------------------
# Document Chunker
# ---------------------------------------------------------------------------
class DocumentChunker:
    """
    Splits raw text into semantically meaningful, overlapping chunks
    suitable for embedding and vector indexing.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        separators: Optional[List[str]] = None,
    ):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or ["\n\n", "\n", ". ", ", ", " ", ""],
            length_function=len,
        )
        logger.info(
            f"[DocumentChunker] Initialized (chunk_size={chunk_size}, overlap={chunk_overlap})"
        )

    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """
        Split a single text block into LangChain Documents with metadata.

        Args:
            text: Raw text content to split.
            metadata: Optional metadata dict to attach to every chunk.

        Returns:
            List of LangChain Document objects.
        """
        if not text or not text.strip():
            return []

        base_meta = metadata or {}
        docs = self.splitter.create_documents(
            texts=[text],
            metadatas=[base_meta],
        )

        # Enrich each chunk with position and content hash
        for idx, doc in enumerate(docs):
            doc.metadata["chunk_index"] = idx
            doc.metadata["chunk_total"] = len(docs)
            doc.metadata["content_hash"] = hashlib.md5(
                doc.page_content.encode()
            ).hexdigest()[:12]

        logger.debug(f"[DocumentChunker] Split text into {len(docs)} chunks")
        return docs

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Split a list of existing Documents into smaller chunks."""
        return self.splitter.split_documents(documents)


# ---------------------------------------------------------------------------
# Salon Knowledge Base (Static Business Knowledge)
# ---------------------------------------------------------------------------

# The canonical salon knowledge base content
SALON_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "category": "services",
        "title": "Signature Precision Haircut",
        "content": (
            "Our Signature Precision Haircut ($85, 60 minutes) includes a premium tailored wash, "
            "precision cut, invigorating scalp massage, and professional style blowout. "
            "Our senior stylists specialize in all hair types and textures. "
            "Recommended maintenance: every 4-6 weeks for optimal shape retention."
        ),
    },
    {
        "category": "services",
        "title": "Balayage & Creative Color",
        "content": (
            "Our Balayage & Creative Color service ($220, 150 minutes) features custom artistic "
            "coloring and toning with high-end premium bond protectors. Includes a consultation "
            "to determine the perfect shade palette for your skin tone and lifestyle. "
            "Our color specialists use Olaplex bond-building treatments to maintain hair integrity. "
            "Touch-up recommended every 8-12 weeks."
        ),
    },
    {
        "category": "services",
        "title": "Hydrating Deep-Cleansing Facial",
        "content": (
            "Our Hydrating Deep-Cleansing Facial ($120, 75 minutes) uses organic advanced botanical "
            "exfoliation, gentle extraction, and antioxidant hydration treatment. "
            "Includes LED light therapy for collagen stimulation and a customized serum application. "
            "Perfect for all skin types, especially dehydrated or congested skin. "
            "Recommended frequency: monthly for optimal results."
        ),
    },
    {
        "category": "services",
        "title": "Himalayan Hot Stone Massage",
        "content": (
            "Our Himalayan Hot Stone Massage ($150, 90 minutes) is a deep tissue somatic therapy "
            "utilizing warm mineral-rich salt rocks sourced from the Himalayas. "
            "Combines Swedish massage techniques with heated stones to release chronic tension, "
            "improve circulation, and promote deep relaxation. "
            "Ideal for stress relief, muscle recovery, and chronic pain management."
        ),
    },
    {
        "category": "policies",
        "title": "Cancellation Policy",
        "content": (
            "SalonAI requires 24-hour advance notice for appointment cancellations. "
            "Late cancellations (less than 24 hours) may incur a 50% service charge. "
            "No-shows will be charged the full service amount. "
            "We understand emergencies happen — please contact us as soon as possible, "
            "and we'll do our best to accommodate rescheduling."
        ),
    },
    {
        "category": "policies",
        "title": "Business Hours & Scheduling",
        "content": (
            "SalonAI is open daily from 9:00 AM to 8:00 PM (UTC). "
            "Last appointment slots are based on service duration to ensure completion before closing. "
            "Online booking is available 24/7 through our AI receptionist Clara. "
            "Walk-ins are welcome based on availability, but we recommend advance booking for "
            "guaranteed slots, especially on weekends."
        ),
    },
    {
        "category": "policies",
        "title": "Pricing & Payment",
        "content": (
            "All prices are displayed inclusive of service costs. "
            "We accept cash, all major credit/debit cards, Apple Pay, and Google Pay. "
            "Gratuities are appreciated but never expected. "
            "Package bundles and loyalty memberships are available — ask our team about "
            "the SalonAI Elite Membership for exclusive discounts and priority booking."
        ),
    },
    {
        "category": "branches",
        "title": "SalonAI Downtown Elite",
        "content": (
            "SalonAI Downtown Elite is located at 100 Enterprise Way, Suite A, Metropolis. "
            "Phone: 555-0100. Email: downtown@salonai.com. "
            "Features 8 styling stations, 2 private facial rooms, and 3 massage suites. "
            "Ample street parking and valet service available on weekends. "
            "Staff includes Senior Stylist Marcus Vance and Master Esthetician Sarah Jenkins."
        ),
    },
    {
        "category": "branches",
        "title": "SalonAI Uptown Oasis",
        "content": (
            "SalonAI Uptown Oasis is located at 450 Serenity Lane, Building 3, Metropolis. "
            "Phone: 555-0200. Email: uptown@salonai.com. "
            "Spa-inspired atmosphere with 6 styling stations, a zen garden waiting area, "
            "and premium tea service. "
            "Staff includes Color Specialist Elena Rostova and Licensed Massage Therapist Kai Chen."
        ),
    },
    {
        "category": "faq",
        "title": "First-Time Visitors",
        "content": (
            "Welcome to SalonAI! For first-time visitors, we recommend arriving 10 minutes early "
            "to complete a brief consultation form. Your stylist will discuss your goals, preferences, "
            "and any concerns before starting the service. "
            "First-time customers receive a complimentary 20% discount on their first service. "
            "No referral needed — just mention you're a new client when booking."
        ),
    },
    {
        "category": "faq",
        "title": "Aftercare & Products",
        "content": (
            "We carry a curated selection of professional-grade hair and skincare products. "
            "Your stylist will recommend specific products based on your service and hair/skin type. "
            "All products are available for purchase in-salon or through our online store. "
            "We offer a 30-day satisfaction guarantee on all retail products."
        ),
    },
    {
        "category": "faq",
        "title": "Group & Event Bookings",
        "content": (
            "SalonAI offers special packages for weddings, proms, corporate events, and group sessions. "
            "Groups of 4+ receive a 10% discount. Bridal packages include trial runs and day-of styling. "
            "Please contact us at least 2 weeks in advance for group bookings to ensure availability. "
            "Private salon buyouts are available for groups of 12+ guests."
        ),
    },
    {
        "category": "loyalty",
        "title": "SalonAI Elite Membership",
        "content": (
            "The SalonAI Elite Membership costs $49/month and includes: "
            "15% off all services, priority booking, complimentary birthday service, "
            "exclusive access to new treatments, and a quarterly product gift box. "
            "Members earn 1 loyalty point per $1 spent. 500 points = $50 credit. "
            "Cancel anytime with no penalty."
        ),
    },
]


def _build_knowledge_documents() -> List[Document]:
    """Convert the salon knowledge base into LangChain Documents."""
    docs = []
    for entry in SALON_KNOWLEDGE_BASE:
        content = f"{entry['title']}\n\n{entry['content']}"
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source": "salon_knowledge_base",
                    "category": entry["category"],
                    "title": entry["title"],
                    "doc_type": "knowledge",
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
    return docs


# ---------------------------------------------------------------------------
# Customer Interaction Indexer (Dynamic from PostgreSQL)
# ---------------------------------------------------------------------------
def build_interaction_documents(
    include_appointments: bool = True,
    include_reviews: bool = True,
    include_leads: bool = True,
    limit: int = 500,
) -> List[Document]:
    """
    Pull customer interaction data from PostgreSQL and convert to LangChain Documents.

    Args:
        include_appointments: Index appointment records.
        include_reviews: Index customer review records.
        include_leads: Index lead records.
        limit: Maximum records to pull per entity type.

    Returns:
        List of LangChain Document objects ready for embedding.
    """
    from db.database import SessionLocal
    from db.models import (
        Appointment, Customer, Service, Staff, Branch,
        Review, Lead, AppointmentStatus, LeadStatus
    )

    logger.info("[Ingest] Building interaction documents from PostgreSQL...")
    documents: List[Document] = []
    session = SessionLocal()

    try:
        # --- Appointments ---
        if include_appointments:
            appointments = (
                session.query(Appointment)
                .order_by(Appointment.start_time.desc())
                .limit(limit)
                .all()
            )
            for appt in appointments:
                customer = session.query(Customer).filter(Customer.id == appt.customer_id).first()
                service = session.query(Service).filter(Service.id == appt.service_id).first()
                staff = session.query(Staff).filter(Staff.id == appt.staff_id).first() if appt.staff_id else None
                branch = session.query(Branch).filter(Branch.id == appt.branch_id).first()

                content_parts = [
                    f"Appointment for {customer.full_name if customer else 'Unknown'}"
                    f" at {branch.name if branch else 'Unknown branch'}.",
                    f"Service: {service.name if service else 'Unknown'}"
                    f" (${float(service.price):.2f}, {service.duration_minutes} min)." if service else "",
                    f"Stylist: {staff.full_name if staff else 'Auto-assigned'}.",
                    f"Date: {appt.start_time.strftime('%Y-%m-%d %H:%M')} to {appt.end_time.strftime('%H:%M')}.",
                    f"Status: {appt.status.value}.",
                ]
                if appt.notes:
                    content_parts.append(f"Notes: {appt.notes}")

                content = " ".join(filter(None, content_parts))

                documents.append(
                    Document(
                        page_content=content,
                        metadata={
                            "source": "postgresql",
                            "doc_type": "appointment",
                            "appointment_id": str(appt.id),
                            "customer_id": str(appt.customer_id),
                            "customer_name": customer.full_name if customer else None,
                            "branch_name": branch.name if branch else None,
                            "service_name": service.name if service else None,
                            "status": appt.status.value,
                            "date": appt.start_time.isoformat(),
                            "ingested_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                )

            logger.info(f"[Ingest] Indexed {len(appointments)} appointments")

        # --- Reviews ---
        if include_reviews:
            reviews = (
                session.query(Review)
                .order_by(Review.created_at.desc())
                .limit(limit)
                .all()
            )
            for review in reviews:
                customer = session.query(Customer).filter(Customer.id == review.customer_id).first()
                branch = session.query(Branch).filter(Branch.id == review.branch_id).first()

                content = (
                    f"Customer review by {customer.full_name if customer else 'Unknown'} "
                    f"at {branch.name if branch else 'Unknown branch'}. "
                    f"Rating: {review.rating}/5 stars. "
                    f"Comment: {review.comment or 'No comment provided.'}. "
                    f"Status: {review.status.value}."
                )

                documents.append(
                    Document(
                        page_content=content,
                        metadata={
                            "source": "postgresql",
                            "doc_type": "review",
                            "review_id": str(review.id),
                            "customer_id": str(review.customer_id),
                            "customer_name": customer.full_name if customer else None,
                            "branch_name": branch.name if branch else None,
                            "rating": review.rating,
                            "ingested_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                )

            logger.info(f"[Ingest] Indexed {len(reviews)} reviews")

        # --- Leads ---
        if include_leads:
            leads = (
                session.query(Lead)
                .order_by(Lead.created_at.desc())
                .limit(limit)
                .all()
            )
            for lead in leads:
                branch = session.query(Branch).filter(Branch.id == lead.branch_id).first() if lead.branch_id else None

                content = (
                    f"Lead: {lead.full_name}. "
                    f"Email: {lead.email or 'N/A'}. Phone: {lead.phone or 'N/A'}. "
                    f"Source: {lead.source or 'Unknown'}. "
                    f"Status: {lead.status.value}. "
                    f"Branch interest: {branch.name if branch else 'Any'}. "
                    f"Notes: {lead.notes or 'No notes.'}"
                )

                documents.append(
                    Document(
                        page_content=content,
                        metadata={
                            "source": "postgresql",
                            "doc_type": "lead",
                            "lead_id": str(lead.id),
                            "lead_name": lead.full_name,
                            "status": lead.status.value,
                            "source_channel": lead.source,
                            "ingested_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                )

            logger.info(f"[Ingest] Indexed {len(leads)} leads")

    except Exception as e:
        logger.error(f"[Ingest] Error building interaction documents: {e}", exc_info=True)
    finally:
        session.close()

    logger.info(f"[Ingest] Total interaction documents built: {len(documents)}")
    return documents


# ---------------------------------------------------------------------------
# RAG Ingestor (Unified Facade)
# ---------------------------------------------------------------------------
class RAGIngestor:
    """
    Unified ingestion facade that orchestrates:
        1. Loading knowledge base and interaction documents
        2. Chunking into embedding-ready fragments
        3. Building and persisting FAISS vector indices

    Manages two separate FAISS indices:
        - `knowledge_index`  → Static salon business knowledge
        - `interaction_index` → Dynamic customer interactions from PostgreSQL
    """

    KNOWLEDGE_INDEX_NAME = "salon_knowledge"
    INTERACTION_INDEX_NAME = "customer_interactions"

    def __init__(
        self,
        index_dir: Optional[str] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        self.index_dir = index_dir or _DEFAULT_INDEX_DIR
        self.embedding_model = get_embedding_model(embedding_config)
        self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # Ensure index directory exists
        os.makedirs(self.index_dir, exist_ok=True)
        logger.info(f"[RAGIngestor] Initialized (index_dir={self.index_dir})")

    def ingest_knowledge_base(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        Build the salon knowledge base FAISS index from static content.

        Args:
            force_rebuild: If True, rebuilds even if an existing index is found.

        Returns:
            Metadata about the ingestion result.
        """
        from langchain_community.vectorstores import FAISS

        index_path = os.path.join(self.index_dir, self.KNOWLEDGE_INDEX_NAME)

        # Check for existing index
        if not force_rebuild and os.path.exists(f"{index_path}.faiss"):
            logger.info("[RAGIngestor] Knowledge base index already exists. Skipping rebuild.")
            return {
                "success": True,
                "action": "skipped",
                "index_path": index_path,
                "message": "Existing index found. Use force_rebuild=True to overwrite.",
            }

        logger.info("[RAGIngestor] Building salon knowledge base index...")

        # Load and chunk knowledge documents
        raw_docs = _build_knowledge_documents()
        chunked_docs = self.chunker.chunk_documents(raw_docs)

        logger.info(f"[RAGIngestor] Chunked {len(raw_docs)} docs → {len(chunked_docs)} chunks")

        # Build FAISS index
        vectorstore = FAISS.from_documents(
            documents=chunked_docs,
            embedding=self.embedding_model,
        )

        # Persist to disk
        vectorstore.save_local(index_path)

        logger.info(f"[RAGIngestor] Knowledge base index saved to {index_path}")
        return {
            "success": True,
            "action": "built",
            "index_name": self.KNOWLEDGE_INDEX_NAME,
            "index_path": index_path,
            "raw_documents": len(raw_docs),
            "chunks_indexed": len(chunked_docs),
        }

    def ingest_interactions(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        Build the customer interaction FAISS index from PostgreSQL data.

        Args:
            force_rebuild: If True, rebuilds even if an existing index is found.

        Returns:
            Metadata about the ingestion result.
        """
        from langchain_community.vectorstores import FAISS

        index_path = os.path.join(self.index_dir, self.INTERACTION_INDEX_NAME)

        if not force_rebuild and os.path.exists(f"{index_path}.faiss"):
            logger.info("[RAGIngestor] Interaction index already exists. Skipping rebuild.")
            return {
                "success": True,
                "action": "skipped",
                "index_path": index_path,
                "message": "Existing index found. Use force_rebuild=True to overwrite.",
            }

        logger.info("[RAGIngestor] Building customer interaction index from PostgreSQL...")

        # Pull from database
        raw_docs = build_interaction_documents()

        if not raw_docs:
            logger.warning("[RAGIngestor] No interaction documents found in database.")
            return {
                "success": True,
                "action": "empty",
                "message": "No interaction records found in the database.",
            }

        # Chunk interaction documents
        chunked_docs = self.chunker.chunk_documents(raw_docs)

        logger.info(f"[RAGIngestor] Chunked {len(raw_docs)} interactions → {len(chunked_docs)} chunks")

        # Build FAISS index
        vectorstore = FAISS.from_documents(
            documents=chunked_docs,
            embedding=self.embedding_model,
        )

        # Persist to disk
        vectorstore.save_local(index_path)

        logger.info(f"[RAGIngestor] Interaction index saved to {index_path}")
        return {
            "success": True,
            "action": "built",
            "index_name": self.INTERACTION_INDEX_NAME,
            "index_path": index_path,
            "raw_documents": len(raw_docs),
            "chunks_indexed": len(chunked_docs),
        }

    def ingest_custom_documents(
        self,
        documents: List[Document],
        index_name: str = "custom",
    ) -> Dict[str, Any]:
        """
        Ingest arbitrary LangChain Documents into a named FAISS index.

        Args:
            documents: List of LangChain Document objects.
            index_name: Name for the FAISS index file.

        Returns:
            Ingestion result metadata.
        """
        from langchain_community.vectorstores import FAISS

        if not documents:
            return {"success": False, "error": "No documents provided."}

        index_path = os.path.join(self.index_dir, index_name)

        chunked = self.chunker.chunk_documents(documents)

        vectorstore = FAISS.from_documents(
            documents=chunked,
            embedding=self.embedding_model,
        )
        vectorstore.save_local(index_path)

        logger.info(f"[RAGIngestor] Custom index '{index_name}' saved ({len(chunked)} chunks)")
        return {
            "success": True,
            "index_name": index_name,
            "index_path": index_path,
            "chunks_indexed": len(chunked),
        }

    def ingest_all(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        Run full ingestion pipeline: knowledge base + customer interactions.

        Args:
            force_rebuild: Rebuild all indices from scratch.

        Returns:
            Combined ingestion results.
        """
        logger.info("[RAGIngestor] Starting full ingestion pipeline...")

        kb_result = self.ingest_knowledge_base(force_rebuild=force_rebuild)
        interaction_result = self.ingest_interactions(force_rebuild=force_rebuild)

        return {
            "success": True,
            "knowledge_base": kb_result,
            "interactions": interaction_result,
        }
