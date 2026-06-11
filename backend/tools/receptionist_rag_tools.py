import os
import logging
import datetime
from typing import Optional, List, Dict, Any
from langchain_community.vectorstores import FAISS

# Project imports
from db.database import SessionLocal
from db.models import KnowledgeDocument, SpecialOffer
from rag.embeddings import get_embedding_model

logger = logging.getLogger(__name__)

# Directory path for Receptionist Knowledge Base FAISS
_RECEPTIONIST_KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "faiss_indices",
    "receptionist_knowledge"
)


def search_receptionist_knowledge(query: str, k: int = 2) -> str:
    """
    Search the dynamic receptionist knowledge base (uploaded policy files, FAQs, and active offers)
    using semantic similarity search. Use this for general salon policies, business hours, FAQs, and active promotions.
    """
    logger.info(f"[RAG Tool] search_receptionist_knowledge: '{query}' (k={k})")
    if not os.path.exists(os.path.join(_RECEPTIONIST_KNOWLEDGE_DIR, "index.faiss")):
        return "The receptionist knowledge base is currently empty or has not been initialized by the admin."

    try:
        embedding_model = get_embedding_model()
        vectorstore = FAISS.load_local(
            _RECEPTIONIST_KNOWLEDGE_DIR, 
            embedding_model, 
            allow_dangerous_deserialization=True
        )

        # Use similarity_search directly to avoid negative-score issues with certain FAISS
        # index types (inner product vs cosine). similarity_search_with_relevance_scores
        # can return negative values with L2/IP FAISS indices which would wrongly filter all results.
        import warnings
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw_res_with_scores = vectorstore.similarity_search_with_relevance_scores(query, k=k)
            # Check if scores are all negative (inner product FAISS issue)
            all_negative = all(score < 0 for _, score in raw_res_with_scores)
            if all_negative:
                # Fall back to plain similarity_search (no score thresholding)
                docs = vectorstore.similarity_search(query, k=k)
                results = [(doc, 1.0) for doc in docs if doc.metadata.get("type") != "placeholder"]
            else:
                # Use low threshold (0.05) to handle FAISS IP/L2 indices with compressed score ranges
                results = [
                    (doc, score) for doc, score in raw_res_with_scores
                    if score >= 0.05 and doc.metadata.get("type") != "placeholder"
                ]
                # If threshold still filters everything, fall back to plain search
                if not results:
                    docs = vectorstore.similarity_search(query, k=k)
                    results = [(doc, 1.0) for doc in docs if doc.metadata.get("type") != "placeholder"]
        except Exception:
            # Fallback to plain similarity search
            docs = vectorstore.similarity_search(query, k=k)
            results = [(doc, 1.0) for doc in docs if doc.metadata.get("type") != "placeholder"]

        if not results:
            return "No matching policies, timings, or active offers were found in the knowledge base."

        lines = ["--- Matches found in Receptionist Knowledge Base ---"]
        for idx, (doc, score) in enumerate(results, 1):
            doc_type = doc.metadata.get("type", "document")
            title = doc.metadata.get("title", "Policy")
            lines.append(f"\n[{idx}] (Source: {title} | Type: {doc_type} | Relevance: {score:.2f})")
            lines.append(doc.page_content)
        lines.append("\n--- End of Context ---")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[RAG Tool] search_receptionist_knowledge failed: {e}", exc_info=True)
        return f"Error searching knowledge base: {str(e)}"


def get_active_offers() -> str:
    """
    Retrieve all current active special promotions and discounts available at the salon.
    """
    logger.info("[RAG Tool] get_active_offers")
    db = SessionLocal()
    try:
        today = datetime.date.today()
        offers = db.query(SpecialOffer).filter(
            SpecialOffer.is_active == True,
            SpecialOffer.is_deleted == False,
            SpecialOffer.start_date <= today,
            SpecialOffer.end_date >= today
        ).all()

        if not offers:
            return "There are no active special offers or promotions currently available at the salon."

        lines = ["--- Active Special Offers & Promotions ---"]
        for offer in offers:
            lines.append(
                f"- {offer.title}: {offer.description} "
                f"({offer.discount_pct}% OFF). Valid from {offer.start_date} to {offer.end_date}."
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[RAG Tool] get_active_offers failed: {e}", exc_info=True)
        return f"Error retrieving active offers: {str(e)}"
    finally:
        db.close()


def _get_active_document_by_type(doc_type: str) -> str:
    """Helper to query the latest active document content from the database."""
    db = SessionLocal()
    try:
        doc = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.document_type == doc_type,
            KnowledgeDocument.is_active == True,
            KnowledgeDocument.is_deleted == False
        ).first()

        if not doc:
            return f"The active policy/information for '{doc_type}' is not configured in the database."

        return f"--- Active {doc.title} (Version: {doc.version}) ---\n{doc.content}"
    except Exception as e:
        logger.error(f"[RAG Tool] _get_active_document_by_type ({doc_type}) failed: {e}", exc_info=True)
        return f"Error retrieving policy: {str(e)}"
    finally:
        db.close()


def get_business_timings() -> str:
    """
    Get the official salon operational hours and scheduling timings.
    """
    logger.info("[RAG Tool] get_business_timings")
    return _get_active_document_by_type("timings")


def get_cancellation_policy() -> str:
    """
    Get the appointment cancellation and modification rules.
    """
    logger.info("[RAG Tool] get_cancellation_policy")
    return _get_active_document_by_type("cancellation_policy")


def get_refund_policy() -> str:
    """
    Get the refund and payment policy of the salon.
    """
    logger.info("[RAG Tool] get_refund_policy")
    return _get_active_document_by_type("refund_policy")


def get_faq_answer(query: str) -> str:
    """
    Search the dynamic receptionist knowledge base specifically for FAQs matching the query.
    """
    logger.info(f"[RAG Tool] get_faq_answer for: '{query}'")
    return search_receptionist_knowledge(query)
