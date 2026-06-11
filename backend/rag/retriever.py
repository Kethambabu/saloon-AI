"""
Semantic Retriever System for SalonAI Workforce RAG Pipeline.

Provides a high-level retrieval interface that:
    1. Loads persisted FAISS indices from disk
    2. Executes semantic similarity search with score filtering
    3. Supports multi-index fusion (knowledge + interactions)
    4. Provides AutoGen agent integration via wrapper tool functions
    5. Offers contextual retrieval with metadata filtering

Architecture:
    FAISSRetriever     →  Single-index retrieval with score thresholding
    SalonRAGRetriever  →  Multi-index fusion retriever (knowledge + interactions)
    Agent Tool Wrappers →  search_salon_knowledge(), search_customer_interactions(),
                           search_all_context() — ready for AutoGen function calling
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple

from langchain_core.documents import Document

from core.config import get_settings
from rag.embeddings import get_embedding_model, EmbeddingConfig

logger = logging.getLogger(__name__)
settings = get_settings()

# Default index directory (mirrors ingest.py)
_DEFAULT_INDEX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "faiss_indices",
)


# ---------------------------------------------------------------------------
# Single-Index FAISS Retriever
# ---------------------------------------------------------------------------
class FAISSRetriever:
    """
    Loads a persisted FAISS index and provides semantic similarity search
    with configurable top-k and relevance score thresholding.
    """

    def __init__(
        self,
        index_name: str,
        index_dir: Optional[str] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
        relevance_threshold: float = 0.3,
    ):
        """
        Args:
            index_name: Name of the FAISS index folder (e.g. 'salon_knowledge').
            index_dir: Directory containing FAISS indices.
            embedding_config: Embedding model configuration (auto-detected if None).
            relevance_threshold: Minimum similarity score to include results (0.0–1.0).
        """
        self.index_name = index_name
        self.index_dir = index_dir or _DEFAULT_INDEX_DIR
        self.relevance_threshold = relevance_threshold
        self._vectorstore = None
        self._embedding_model = get_embedding_model(embedding_config)

        logger.info(
            f"[FAISSRetriever] Initialized for index '{index_name}' "
            f"(threshold={relevance_threshold})"
        )

    @property
    def index_path(self) -> str:
        """Full path to the FAISS index folder."""
        return os.path.join(self.index_dir, self.index_name)

    @property
    def is_loaded(self) -> bool:
        """Check if the vectorstore is loaded in memory."""
        return self._vectorstore is not None

    @property
    def index_exists(self) -> bool:
        """Check if the persisted index file exists on disk."""
        return os.path.exists(f"{self.index_path}.faiss") or os.path.isdir(self.index_path)

    def load(self) -> bool:
        """
        Load the FAISS index from disk into memory.

        Returns:
            True if loaded successfully, False if index not found.
        """
        from langchain_community.vectorstores import FAISS

        if not self.index_exists:
            logger.warning(f"[FAISSRetriever] Index '{self.index_name}' not found at {self.index_path}")
            return False

        try:
            self._vectorstore = FAISS.load_local(
                self.index_path,
                self._embedding_model,
                allow_dangerous_deserialization=True,
            )
            logger.info(f"[FAISSRetriever] Loaded index '{self.index_name}' into memory")
            return True
        except Exception as e:
            logger.error(f"[FAISSRetriever] Failed to load index '{self.index_name}': {e}", exc_info=True)
            return False

    def _ensure_loaded(self) -> None:
        """Lazy-load the index on first query."""
        if not self.is_loaded:
            if not self.load():
                raise RuntimeError(
                    f"FAISS index '{self.index_name}' not found. "
                    f"Run RAGIngestor.ingest_all() first to build indices."
                )

    def search(
        self,
        query: str,
        k: int = 2,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Semantic similarity search with relevance scores.

        Args:
            query: Natural language search query.
            k: Maximum number of results to return.
            filter_metadata: Optional metadata key-value filters (post-retrieval).

        Returns:
            List of (Document, score) tuples sorted by relevance (highest first).
        """
        self._ensure_loaded()

        logger.info(
            f"[FAISSRetriever] Searching '{self.index_name}' for: '{query[:80]}...' (k={k})"
        )

        # FAISS similarity_search_with_score returns (doc, distance)
        # Lower distance = more similar for L2; we normalize to a relevance score
        raw_results = self._vectorstore.similarity_search_with_relevance_scores(
            query=query,
            k=k * 2,  # Over-fetch to account for threshold filtering
        )

        # Apply relevance threshold
        filtered = [
            (doc, score) for doc, score in raw_results
            if score >= self.relevance_threshold
        ]

        # Apply metadata filter (post-retrieval)
        if filter_metadata:
            filtered = [
                (doc, score) for doc, score in filtered
                if all(doc.metadata.get(key) == val for key, val in filter_metadata.items())
            ]

        # Sort by score descending and limit to k
        filtered.sort(key=lambda x: x[1], reverse=True)
        results = filtered[:k]

        logger.info(
            f"[FAISSRetriever] Found {len(results)} results above threshold "
            f"(from {len(raw_results)} raw)"
        )
        return results

    def search_text(
        self,
        query: str,
        k: int = 2,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search and return results as structured dictionaries.

        Args:
            query: Search query.
            k: Max results.
            filter_metadata: Optional metadata filters.

        Returns:
            List of result dicts with content, score, and metadata.
        """
        results = self.search(query=query, k=k, filter_metadata=filter_metadata)
        return [
            {
                "content": doc.page_content,
                "score": round(float(score), 4),
                "metadata": doc.metadata,
            }
            for doc, score in results
        ]


# ---------------------------------------------------------------------------
# Multi-Index Fusion Retriever
# ---------------------------------------------------------------------------
class SalonRAGRetriever:
    """
    Enterprise multi-index retriever that fuses results from:
        1. Salon Knowledge Base (services, policies, FAQs)
        2. Customer Interactions (appointments, reviews, leads)

    Supports independent and combined search modes with unified ranking.
    """

    def __init__(
        self,
        index_dir: Optional[str] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
        knowledge_threshold: float = 0.3,
        interaction_threshold: float = 0.25,
    ):
        self.index_dir = index_dir or _DEFAULT_INDEX_DIR
        self._embedding_config = embedding_config

        self.knowledge_retriever = FAISSRetriever(
            index_name="receptionist_knowledge",
            index_dir=self.index_dir,
            embedding_config=embedding_config,
            relevance_threshold=knowledge_threshold,
        )

        self.interaction_retriever = FAISSRetriever(
            index_name="customer_interactions",
            index_dir=self.index_dir,
            embedding_config=embedding_config,
            relevance_threshold=interaction_threshold,
        )

        logger.info("[SalonRAGRetriever] Multi-index retriever initialized")

    def search_knowledge(
        self,
        query: str,
        k: int = 2,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search the receptionist knowledge base (services, policies, FAQs, branch info).

        Args:
            query: Natural language query.
            k: Max results.
            category: Optional category filter ('services', 'policies', 'faq', 'branches', 'loyalty').

        Returns:
            List of result dicts.
        """
        filter_meta = {}
        if category:
            category_lower = category.lower()
            if category_lower in ["policies", "policy"]:
                filter_meta["type"] = "policy"
            elif category_lower == "timings":
                filter_meta["document_type"] = "timings"
            elif category_lower in ["cancellation", "cancellation_policy"]:
                filter_meta["document_type"] = "cancellation_policy"
            elif category_lower in ["refund", "refund_policy"]:
                filter_meta["document_type"] = "refund_policy"
            elif category_lower in ["offers", "offer", "promotions", "promotion"]:
                filter_meta["type"] = "offer"
            elif category_lower in ["services", "service"]:
                filter_meta["document_type"] = "services"
            elif category_lower in ["branches", "branch"]:
                filter_meta["document_type"] = "branches"
            elif category_lower in ["faq"]:
                filter_meta["document_type"] = "faq"
            elif category_lower in ["loyalty"]:
                filter_meta["document_type"] = "loyalty"
            else:
                filter_meta["category"] = category

        return self.knowledge_retriever.search_text(
            query=query, k=k, filter_metadata=filter_meta or None,
        )

    def search_interactions(
        self,
        query: str,
        k: int = 2,
        doc_type: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search customer interactions (appointments, reviews, leads).

        Args:
            query: Natural language query.
            k: Max results.
            doc_type: Filter by type ('appointment', 'review', 'lead').
            customer_name: Filter by customer name.

        Returns:
            List of result dicts.
        """
        filter_meta = {}
        if doc_type:
            filter_meta["doc_type"] = doc_type
        if customer_name:
            filter_meta["customer_name"] = customer_name

        return self.interaction_retriever.search_text(
            query=query, k=k, filter_metadata=filter_meta or None,
        )

    def search_all(
        self,
        query: str,
        k: int = 2,
        knowledge_weight: float = 1.0,
        interaction_weight: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Fused search across both knowledge base and customer interactions.
        Results are merged and re-ranked by weighted relevance score.

        Args:
            query: Natural language query.
            k: Max total results.
            knowledge_weight: Score multiplier for knowledge results (default 1.0).
            interaction_weight: Score multiplier for interaction results (default 1.0).

        Returns:
            Unified ranked list of results from both indices.
        """
        logger.info(f"[SalonRAGRetriever] Fused search: '{query[:80]}...'")

        all_results = []

        # Search knowledge base
        try:
            kb_results = self.knowledge_retriever.search(query=query, k=k)
            for doc, score in kb_results:
                all_results.append({
                    "content": doc.page_content,
                    "score": round(float(score) * knowledge_weight, 4),
                    "source_index": "knowledge",
                    "metadata": doc.metadata,
                })
        except RuntimeError:
            logger.warning("[SalonRAGRetriever] Knowledge index not available")

        # Search interactions
        try:
            int_results = self.interaction_retriever.search(query=query, k=k)
            for doc, score in int_results:
                all_results.append({
                    "content": doc.page_content,
                    "score": round(float(score) * interaction_weight, 4),
                    "source_index": "interactions",
                    "metadata": doc.metadata,
                })
        except RuntimeError:
            logger.warning("[SalonRAGRetriever] Interaction index not available")

        # Re-rank by fused score
        all_results.sort(key=lambda x: x["score"], reverse=True)

        results = all_results[:k]
        logger.info(f"[SalonRAGRetriever] Fused search returned {len(results)} results")
        return results

    def get_context_for_agent(
        self,
        query: str,
        k: int = 2,
        max_context_chars: int = 2000,
    ) -> str:
        """
        Retrieve and format context as a text block suitable for injecting
        into an AutoGen agent's system message or task prompt.

        Args:
            query: The user's query.
            k: Number of context chunks to retrieve.
            max_context_chars: Maximum character length for the context block.

        Returns:
            Formatted context string for agent consumption.
        """
        results = self.search_all(query=query, k=k)

        if not results:
            return ""

        context_parts = ["--- Relevant Context from SalonAI Knowledge Base ---"]
        char_count = 0

        for i, result in enumerate(results, 1):
            source = result.get("source_index", "unknown")
            score = result.get("score", 0)
            content = result["content"]

            entry = f"\n[{i}] ({source}, relevance: {score:.2f})\n{content}"

            if char_count + len(entry) > max_context_chars:
                break

            context_parts.append(entry)
            char_count += len(entry)

        context_parts.append("\n--- End of Context ---")
        return "\n".join(context_parts)

    def get_status(self) -> Dict[str, Any]:
        """Return status of all indices."""
        return {
            "knowledge_index": {
                "exists": self.knowledge_retriever.index_exists,
                "loaded": self.knowledge_retriever.is_loaded,
            },
            "interaction_index": {
                "exists": self.interaction_retriever.index_exists,
                "loaded": self.interaction_retriever.is_loaded,
            },
            "index_dir": self.index_dir,
        }


# ---------------------------------------------------------------------------
# Singleton Retriever Instance
# ---------------------------------------------------------------------------
_retriever_instance: Optional[SalonRAGRetriever] = None


def get_retriever(
    index_dir: Optional[str] = None,
    embedding_config: Optional[EmbeddingConfig] = None,
) -> SalonRAGRetriever:
    """
    Get or create the singleton SalonRAGRetriever instance.

    Args:
        index_dir: Override index directory.
        embedding_config: Override embedding config.

    Returns:
        Configured SalonRAGRetriever instance.
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = SalonRAGRetriever(
            index_dir=index_dir,
            embedding_config=embedding_config,
        )
    return _retriever_instance


# ---------------------------------------------------------------------------
# AutoGen Agent Tool Wrappers
# ---------------------------------------------------------------------------
def search_salon_knowledge(
    query: str,
    category: Optional[str] = None,
    k: int = 2,
) -> str:
    """
    Search the salon knowledge base for information about services, policies,
    FAQs, branch locations, and membership programs.

    Args:
        query: Natural language search query (e.g. 'What is the cancellation policy?').
        category: Optional category filter: 'services', 'policies', 'faq', 'branches', or 'loyalty'.
        k: Maximum number of results to return (default 5).
    """
    logger.info(f"[RAG Tool] search_salon_knowledge(query='{query[:60]}', category={category})")
    try:
        retriever = get_retriever()
        results = retriever.search_knowledge(query=query, k=k, category=category)
        return str({"success": True, "results": results, "total": len(results)})
    except Exception as e:
        logger.error(f"[RAG Tool] Knowledge search failed: {e}", exc_info=True)
        return str({"success": False, "error": str(e)})


def search_customer_interactions(
    query: str,
    doc_type: Optional[str] = None,
    customer_name: Optional[str] = None,
    k: int = 2,
) -> str:
    """
    Search customer interaction history including past appointments,
    reviews, and lead records using semantic similarity.

    Args:
        query: Natural language search query (e.g. 'Alice Smith past appointments').
        doc_type: Optional filter: 'appointment', 'review', or 'lead'.
        customer_name: Optional customer name to filter results.
        k: Maximum number of results to return (default 5).
    """
    logger.info(f"[RAG Tool] search_customer_interactions(query='{query[:60]}', type={doc_type})")
    try:
        retriever = get_retriever()
        results = retriever.search_interactions(
            query=query, k=k, doc_type=doc_type, customer_name=customer_name,
        )
        return str({"success": True, "results": results, "total": len(results)})
    except Exception as e:
        logger.error(f"[RAG Tool] Interaction search failed: {e}", exc_info=True)
        return str({"success": False, "error": str(e)})


def search_all_context(
    query: str,
    k: int = 2,
) -> str:
    """
    Search across ALL salon knowledge and customer interaction history.
    Returns a fused, ranked list of the most relevant context from both indices.

    Args:
        query: Natural language search query.
        k: Maximum number of total results to return (default 5).
    """
    logger.info(f"[RAG Tool] search_all_context(query='{query[:60]}')")
    try:
        retriever = get_retriever()
        results = retriever.search_all(query=query, k=k)
        return str({"success": True, "results": results, "total": len(results)})
    except Exception as e:
        logger.error(f"[RAG Tool] Full context search failed: {e}", exc_info=True)
        return str({"success": False, "error": str(e)})


def get_agent_context(query: str, k: int = 2) -> str:
    """
    Retrieve formatted context block from the RAG system suitable for
    injecting into an AI agent's prompt for context-aware responses.

    Args:
        query: The user's query to find relevant context for.
        k: Number of context chunks to retrieve (default 3).
    """
    logger.info(f"[RAG Tool] get_agent_context(query='{query[:60]}')")
    try:
        retriever = get_retriever()
        context = retriever.get_context_for_agent(query=query, k=k)
        if context:
            return context
        return "No relevant context found in the knowledge base."
    except Exception as e:
        logger.error(f"[RAG Tool] Context retrieval failed: {e}", exc_info=True)
        return f"Context retrieval error: {str(e)}"


# ============================================================================
# HIERARCHICAL LONG-TERM AGENT MEMORY RETRIEVAL TOOLS
# ============================================================================

def search_agent_memory(
    agent_name: str, 
    query: str, 
    entity_id: Optional[str] = None,
    k: int = 3
) -> str:
    """
    Search the agent's memory hierarchically: Yearly -> Monthly -> Weekly -> Daily.
    Collect results and return a formatted text context.
    """
    logger.info(f"[RAG Tool] search_agent_memory(agent={agent_name}, query='{query[:50]}', entity_id={entity_id})")
    
    levels = ["yearly", "monthly", "weekly", "daily"]
    results = []
    
    try:
        from rag.embeddings import get_embedding_model
        embedding_model = get_embedding_model()
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        return f"Memory search error: {e}"
        
    for level in levels:
        index_path = os.path.join(_DEFAULT_INDEX_DIR, agent_name, level)
        if not os.path.exists(os.path.join(index_path, "index.faiss")):
            continue
            
        try:
            from langchain_community.vectorstores import FAISS
            vectorstore = FAISS.load_local(index_path, embedding_model, allow_dangerous_deserialization=True)
            
            # Formulate filter for customer and staff
            filter_meta = {}
            if entity_id:
                filter_meta[f"{agent_name}_id"] = str(entity_id)
                
            raw_res = vectorstore.similarity_search_with_relevance_scores(query, k=k)
            
            # Apply threshold & metadata filter
            for doc, score in raw_res:
                if score >= 0.25:  # relevance threshold
                    if filter_meta:
                        if all(doc.metadata.get(key) == val for key, val in filter_meta.items()):
                            results.append((doc, score, level))
                    else:
                        results.append((doc, score, level))
        except Exception as e:
            logger.warning(f"Failed to search {agent_name}/{level} index: {e}")
            
    if not results:
        return f"No relevant memory found for {agent_name} assistant."
        
    # Format combined memories
    lines = [f"--- Relevant Memories from {agent_name.capitalize()} long-term memory ---"]
    results.sort(key=lambda x: x[1], reverse=True)
    
    for idx, (doc, score, level) in enumerate(results[:5], 1):
        lines.append(f"\n[{idx}] ({level.capitalize()} Memory, relevance: {score:.2f})")
        lines.append(doc.page_content)
        
    lines.append("\n--- End of Memory Context ---")
    return "\n".join(lines)


def search_receptionist_memory(query: str) -> str:
    """
    Search receptionist long-term memory across yearly, monthly, weekly, and daily summaries.
    """
    return search_agent_memory("receptionist", query)


def get_current_query_context() -> str:
    """Attempt to get current query context from active agents or contextvars."""
    try:
        from core.query_context import get_query_context
        ctx = get_query_context()
        if ctx:
            return ctx
    except ImportError:
        pass

    context = ""
    try:
        from agents.receptionist_agent import ReceptionistAgent
        context += (getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "") or "") + "\n"
    except ImportError:
        pass

    try:
        from agents.staff_assistant_agent import StaffAssistantAgent
        context += (getattr(StaffAssistantAgent, "CURRENT_QUERY_CONTEXT", "") or "") + "\n"
    except ImportError:
        pass

    return context


def search_customer_memory(query: str, customer_id: Optional[str] = None) -> str:
    """
    Search customer-specific long-term memory profiles across yearly, monthly, weekly, and daily summaries.
    """
    from db.database import SessionLocal
    from db.models import Customer
    from utils.entity_resolver import resolve_customer
    import uuid

    resolved_customer_id = None
    db = SessionLocal()
    try:
        # Check if customer_id is provided and is a valid UUID
        if customer_id:
            try:
                uuid.UUID(str(customer_id))
                resolved_customer_id = str(customer_id)
            except ValueError:
                # customer_id was provided but is not a valid UUID (e.g. it's a name)
                res = resolve_customer(customer_id, db, raise_on_missing=False)
                if res:
                    resolved_customer_id = str(res)

        # If not resolved yet, scan the query or current agent query context for any customer name/ID
        if not resolved_customer_id:
            all_contexts = [query]
            agent_ctx = get_current_query_context()
            if agent_ctx:
                all_contexts.append(agent_ctx)
            
            # 1. Search for customer by name in the contexts
            active_customers = db.query(Customer).filter(Customer.is_active == True).all()
            
            # Check full name matches first
            for cust in active_customers:
                cust_full_name = f"{cust.first_name} {cust.last_name}".lower()
                for ctx in all_contexts:
                    if cust_full_name in ctx.lower():
                        resolved_customer_id = str(cust.id)
                        break
                if resolved_customer_id:
                    break

            # If still not resolved, check first name/last name matches
            if not resolved_customer_id:
                for cust in active_customers:
                    first = cust.first_name.lower()
                    last = cust.last_name.lower()
                    for ctx in all_contexts:
                        if len(first) > 2 and first in ctx.lower():
                            resolved_customer_id = str(cust.id)
                            break
                        if len(last) > 2 and last in ctx.lower():
                            resolved_customer_id = str(cust.id)
                            break
                    if resolved_customer_id:
                        break

            # If still not resolved, check if there's any customer ID resolved from the receptionist context
            if not resolved_customer_id:
                try:
                    from agents.receptionist_agent import get_query_customer_id
                    cust_id = get_query_customer_id()
                    if cust_id:
                        resolved_customer_id = cust_id
                except ImportError:
                    pass
    except Exception as e:
        logger.error(f"Error resolving customer in search_customer_memory: {e}")
    finally:
        db.close()

    if not resolved_customer_id:
        return "No customer_id provided or resolved from query context. Please make sure customer context is available."
    
    return search_agent_memory("customer", query, entity_id=resolved_customer_id)


def search_staff_memory(query: str, staff_id: Optional[str] = None) -> str:
    """
    Search staff-specific performance and scheduling memory across yearly, monthly, weekly, and daily summaries.
    """
    from db.database import SessionLocal
    from db.models import Staff
    from utils.entity_resolver import resolve_staff
    import uuid

    resolved_staff_id = None
    db = SessionLocal()
    try:
        active_staff = db.query(Staff).filter(Staff.is_active == True).all()

        # 1. First, check if the query text explicitly mentions an active staff member's name.
        # This prevents the LLM from bypassing access checks by passing the logged-in staff ID
        # when the user query is actually asking about another staff member.
        for staff in active_staff:
            staff_full_name = f"{staff.first_name} {staff.last_name}".lower()
            if staff_full_name in query.lower():
                resolved_staff_id = str(staff.id)
                break
                
        # Look for first/last name in the query next (longer names first to avoid false matches)
        if not resolved_staff_id:
            sorted_staff = sorted(active_staff, key=lambda s: max(len(s.first_name), len(s.last_name)), reverse=True)
            for staff in sorted_staff:
                first = staff.first_name.lower()
                last = staff.last_name.lower()
                if (len(first) > 2 and first in query.lower()) or (len(last) > 2 and last in query.lower()):
                    resolved_staff_id = str(staff.id)
                    break

        # 2. If not resolved from query text, check if a staff_id parameter was provided
        if not resolved_staff_id and staff_id:
            try:
                uuid.UUID(str(staff_id))
                resolved_staff_id = str(staff_id)
            except ValueError:
                # staff_id was provided but is not a valid UUID (e.g. it's a name)
                res = resolve_staff(staff_id, db, raise_on_missing=False)
                if res:
                    resolved_staff_id = str(res)

        # 3. If still not resolved, check the wider agent context (including system context)
        if not resolved_staff_id:
            agent_ctx = get_current_query_context()
            if agent_ctx:
                # Look for full name in context
                for staff in active_staff:
                    staff_full_name = f"{staff.first_name} {staff.last_name}".lower()
                    if staff_full_name in agent_ctx.lower():
                        resolved_staff_id = str(staff.id)
                        break
                
                # Look for first/last name in context
                if not resolved_staff_id:
                    sorted_staff = sorted(active_staff, key=lambda s: max(len(s.first_name), len(s.last_name)), reverse=True)
                    for staff in sorted_staff:
                        first = staff.first_name.lower()
                        last = staff.last_name.lower()
                        if (len(first) > 2 and first in agent_ctx.lower()) or (len(last) > 2 and last in agent_ctx.lower()):
                            resolved_staff_id = str(staff.id)
                            break
                
                # Look for the logged-in ID in context
                if not resolved_staff_id and "ID: " in agent_ctx:
                    try:
                        parts = agent_ctx.split("ID: ")
                        if len(parts) > 1:
                            potential_id = parts[1].split(",")[0].strip()
                            uuid.UUID(potential_id)
                            resolved_staff_id = potential_id
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Error resolving staff in search_staff_memory: {e}")
    finally:
        db.close()

    if not resolved_staff_id:
        return "No staff_id provided. Please provide a valid staff_id to query staff memory."
        
    from core.query_context import check_staff_access
    access_denied = check_staff_access(resolved_staff_id)
    if access_denied:
        return access_denied

    return search_agent_memory("staff", query, entity_id=resolved_staff_id)


def search_lead_memory(query: str) -> str:
    """
    Search lead follow-up campaign memory across yearly, monthly, weekly, and daily summaries.
    """
    return search_agent_memory("lead", query)


def search_upsell_memory(query: str) -> str:
    """
    Search upsell strategy memory across yearly, monthly, weekly, and daily summaries.
    """
    return search_agent_memory("upsell", query)


def search_reputation_memory(query: str) -> str:
    """
    Search reputation and review templates memory across yearly, monthly, weekly, and daily summaries.
    """
    return search_agent_memory("reputation", query)


def search_bi_memory(query: str) -> str:
    """
    Search business intelligence summaries and corporate reports across yearly, monthly, weekly, and daily memories.
    """
    return search_agent_memory("business_intelligence", query)
