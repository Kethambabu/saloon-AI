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
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception as e:
    # Fallback to a custom pure-Python implementation when PyTorch DLL loading errors prevent importing langchain-text-splitters
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import RecursiveCharacterTextSplitter from langchain_text_splitters: {e}. Using pure-Python fallback.")
    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, separators: Optional[List[str]] = None, length_function = len):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.separators = separators or ["\n\n", "\n", ". ", ", ", " ", ""]
            self.length_function = length_function

        def split_text(self, text: str) -> List[str]:
            return self._split_text(text, self.separators)

        def _split_text(self, text: str, separators: List[str]) -> List[str]:
            if len(text) <= self.chunk_size:
                return [text]
            if not separators:
                return [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]
            separator = separators[0]
            if separator == "":
                splits = list(text)
            else:
                splits = text.split(separator)
            chunks = []
            current_chunk = []
            current_len = 0
            for part in splits:
                part_str = part + separator if separator != "" else part
                if len(part_str) > self.chunk_size:
                    if current_chunk:
                        chunks.append("".join(current_chunk))
                        current_chunk = []
                        current_len = 0
                    sub_splits = self._split_text(part, separators[1:])
                    chunks.extend(sub_splits)
                else:
                    if current_len + len(part_str) > self.chunk_size:
                        if current_chunk:
                            chunks.append("".join(current_chunk))
                        overlap_str = "".join(current_chunk)
                        overlap_len = len(overlap_str)
                        if overlap_len > self.chunk_overlap:
                            current_chunk = [overlap_str[-self.chunk_overlap:], part_str]
                            current_len = self.chunk_overlap + len(part_str)
                        else:
                            current_chunk = [overlap_str, part_str] if overlap_str else [part_str]
                            current_len = overlap_len + len(part_str)
                    else:
                        current_chunk.append(part_str)
                        current_len += len(part_str)
            if current_chunk:
                chunks.append("".join(current_chunk))
            return [c.rstrip(separator) if separator != "" else c for c in chunks]

        def create_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None) -> List[Document]:
            documents = []
            for i, text in enumerate(texts):
                meta = metadatas[i] if metadatas and i < len(metadatas) else {}
                chunks = self.split_text(text)
                for chunk in chunks:
                    documents.append(Document(page_content=chunk, metadata=meta.copy()))
            return documents

        def split_documents(self, documents: List[Document]) -> List[Document]:
            output = []
            for doc in documents:
                chunks = self.split_text(doc.page_content)
                for chunk in chunks:
                    output.append(Document(page_content=chunk, metadata=doc.metadata.copy()))
            return output

from core.config import get_settings
from infrastructure.rag.embeddings import get_embedding_model, EmbeddingConfig

logger = logging.getLogger(__name__)
settings = get_settings()

# Default persistence directory for FAISS indices
_DEFAULT_INDEX_DIR = os.path.join(settings.data_dir, "faiss_indices")


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
        chunk_size: int = 500,
        chunk_overlap: int = 50,
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
# Salon Knowledge Base (Static Business Knowledge RAG #1) was removed from here.
# Dynamic business policies are now managed via RAG #3 (receptionist_knowledge) and stored in the database.


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
    from infrastructure.db.database import SessionLocal
    from infrastructure.db.models import (
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
        1. Loading interaction documents
        2. Chunking into embedding-ready fragments
        3. Building and persisting FAISS vector indices

    Manages FAISS index for dynamic customer interactions from PostgreSQL.
    """

    INTERACTION_INDEX_NAME = "customer_interactions"

    def __init__(
        self,
        index_dir: Optional[str] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.index_dir = index_dir or _DEFAULT_INDEX_DIR
        self.embedding_model = get_embedding_model(embedding_config)
        self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # Ensure index directory exists
        os.makedirs(self.index_dir, exist_ok=True)
        logger.info(f"[RAGIngestor] Initialized (index_dir={self.index_dir})")

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
        Run full ingestion pipeline: customer interactions.

        Args:
            force_rebuild: Rebuild all indices from scratch.

        Returns:
            Combined ingestion results.
        """
        logger.info("[RAGIngestor] Starting customer interaction ingestion...")

        interaction_result = self.ingest_interactions(force_rebuild=force_rebuild)

        return {
            "success": True,
            "interactions": interaction_result,
        }

