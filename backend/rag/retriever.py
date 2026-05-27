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
        k: int = 5,
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
        k: int = 5,
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
            index_name="salon_knowledge",
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
        k: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search the salon knowledge base (services, policies, FAQs, branch info).

        Args:
            query: Natural language query.
            k: Max results.
            category: Optional category filter ('services', 'policies', 'faq', 'branches', 'loyalty').

        Returns:
            List of result dicts.
        """
        filter_meta = {"category": category} if category else None
        return self.knowledge_retriever.search_text(
            query=query, k=k, filter_metadata=filter_meta,
        )

    def search_interactions(
        self,
        query: str,
        k: int = 5,
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
        k: int = 5,
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
        k: int = 3,
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
    k: int = 5,
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
    k: int = 5,
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
    k: int = 5,
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


def get_agent_context(query: str, k: int = 3) -> str:
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
