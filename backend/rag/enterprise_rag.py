"""
Enterprise RAG System — Phase 2 Architecture.

Replaces fragmented multi-domain RAG with five unified, named RAG domains:

  POLICY_RAG    — Salon policies, FAQs, business hours, cancellation rules
  CUSTOMER_RAG  — Customer interaction history, styling notes, preferences
  STAFF_RAG     — Staff performance, scheduling notes, expertise profiles
  LEAD_RAG      — CRM lead nurturing playbooks, follow-up templates
  BUSINESS_RAG  — Business KPI history, BI memory, cohort snapshots

Each domain is a named FAISS index with:
  - Semantic similarity search
  - Metadata filtering
  - Tenant-scoped retrieval (prefix-based index isolation)
  - Score thresholding

Backward compatibility: existing search_knowledge_base() continues to work
by mapping old domain names to the new 5-domain system.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# FAISS index root
_INDEX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "faiss_indices",
)


# ---------------------------------------------------------------------------
# RAG Domain Enum
# ---------------------------------------------------------------------------
class RAGDomain(str, Enum):
    """The five canonical RAG domains for Phase 2."""
    POLICY_RAG   = "POLICY_RAG"
    CUSTOMER_RAG = "CUSTOMER_RAG"
    STAFF_RAG    = "STAFF_RAG"
    LEAD_RAG     = "LEAD_RAG"
    BUSINESS_RAG = "BUSINESS_RAG"


# ---------------------------------------------------------------------------
# Domain → FAISS Index Name Mapping
# ---------------------------------------------------------------------------
_DOMAIN_INDEX_MAP: Dict[RAGDomain, List[str]] = {
    RAGDomain.POLICY_RAG:   ["receptionist_knowledge", "salon_knowledge"],
    RAGDomain.CUSTOMER_RAG: ["customer_interactions", "customer"],
    RAGDomain.STAFF_RAG:    ["staff"],
    RAGDomain.LEAD_RAG:     ["lead"],
    RAGDomain.BUSINESS_RAG: ["bi_memory"],
}

# Legacy domain → new RAG domain mapping (backward compatibility)
_LEGACY_DOMAIN_MAP: Dict[str, RAGDomain] = {
    "policies":          RAGDomain.POLICY_RAG,
    "faq":               RAGDomain.POLICY_RAG,
    "business_hours":    RAGDomain.POLICY_RAG,
    "cancellation_policy": RAGDomain.POLICY_RAG,
    "refund_policy":     RAGDomain.POLICY_RAG,
    "offers":            RAGDomain.POLICY_RAG,
    "customer_styling":  RAGDomain.CUSTOMER_RAG,
    "interactions":      RAGDomain.CUSTOMER_RAG,
    "lead_memory":       RAGDomain.LEAD_RAG,
    "upsell_memory":     RAGDomain.LEAD_RAG,
    "reputation_memory": RAGDomain.CUSTOMER_RAG,
    "bi_memory":         RAGDomain.BUSINESS_RAG,
    "staff_memory":      RAGDomain.STAFF_RAG,
    "all_context":       None,  # Special: search all domains
}


# ---------------------------------------------------------------------------
# Single Domain Retriever
# ---------------------------------------------------------------------------
class DomainRetriever:
    """
    Retrieves context from a single named RAG domain.

    Supports:
      - Lazy FAISS index loading
      - Multi-index fallback (tries secondary index if primary is missing)
      - Tenant-scoped index selection (prefix: {tenant_id}/{index_name})
      - Relevance score thresholding
    """

    def __init__(
        self,
        domain: RAGDomain,
        tenant_id: str = "default",
        threshold: float = 0.25,
    ) -> None:
        self.domain = domain
        self.tenant_id = tenant_id
        self.threshold = threshold
        self._vectorstore = None
        self._loaded_index: Optional[str] = None

    def _resolve_index_path(self, index_name: str) -> str:
        """Resolve index path with tenant isolation."""
        # Try tenant-scoped first, fall back to shared
        tenant_path = os.path.join(_INDEX_DIR, self.tenant_id, index_name)
        shared_path = os.path.join(_INDEX_DIR, index_name)
        if os.path.exists(tenant_path) or os.path.isdir(tenant_path):
            return tenant_path
        return shared_path

    def _load(self) -> bool:
        """Lazy-load the first available FAISS index for this domain."""
        try:
            from langchain_community.vectorstores import FAISS
            from rag.embeddings import get_embedding_model
            embed = get_embedding_model()
        except ImportError:
            logger.warning("[DomainRetriever] FAISS or embedding not available.")
            return False

        candidate_indices = _DOMAIN_INDEX_MAP.get(self.domain, [])
        for idx_name in candidate_indices:
            path = self._resolve_index_path(idx_name)
            faiss_file = os.path.join(path, "index.faiss")
            if os.path.exists(faiss_file) or os.path.isdir(path):
                try:
                    self._vectorstore = FAISS.load_local(
                        path, embed, allow_dangerous_deserialization=True
                    )
                    self._loaded_index = idx_name
                    logger.info(
                        "[DomainRetriever] Loaded domain=%s index=%s",
                        self.domain.value, idx_name
                    )
                    return True
                except Exception as exc:
                    logger.warning(
                        "[DomainRetriever] Failed to load %s: %s", path, exc
                    )
        logger.warning(
            "[DomainRetriever] No index available for domain=%s tenant=%s",
            self.domain.value, self.tenant_id
        )
        return False

    def search(
        self,
        query: str,
        k: int = 3,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic similarity search within this domain.

        Args:
            query:           Natural language query.
            k:               Max results.
            filter_metadata: Post-retrieval metadata filter.

        Returns:
            List of {content, score, metadata, domain} dicts.
        """
        if self._vectorstore is None:
            if not self._load():
                return []

        try:
            raw = self._vectorstore.similarity_search_with_relevance_scores(
                query=query, k=k * 2
            )
        except Exception as exc:
            logger.error(
                "[DomainRetriever] Search failed domain=%s: %s",
                self.domain.value, exc
            )
            return []

        results = []
        for doc, score in raw:
            if score < self.threshold:
                continue
            if filter_metadata:
                if not all(doc.metadata.get(k) == v for k, v in filter_metadata.items()):
                    continue
            results.append({
                "content":  doc.page_content,
                "score":    round(float(score), 4),
                "metadata": doc.metadata,
                "domain":   self.domain.value,
                "index":    self._loaded_index,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]


# ---------------------------------------------------------------------------
# Enterprise RAG Manager
# ---------------------------------------------------------------------------
class EnterpriseRAGManager:
    """
    Manages all 5 RAG domains with per-tenant isolation.

    Usage:
        rag = get_rag_manager()
        results = rag.search(RAGDomain.POLICY_RAG, "cancellation policy", tenant_id="salon-a")
        context  = rag.get_context("What are your hours?", domains=[RAGDomain.POLICY_RAG])
    """

    def __init__(self) -> None:
        # Domain → tenant → retriever
        self._retrievers: Dict[str, Dict[str, DomainRetriever]] = {}

    def _get_retriever(self, domain: RAGDomain, tenant_id: str) -> DomainRetriever:
        """Get or create a domain retriever for a tenant."""
        domain_key = domain.value
        if domain_key not in self._retrievers:
            self._retrievers[domain_key] = {}
        if tenant_id not in self._retrievers[domain_key]:
            self._retrievers[domain_key][tenant_id] = DomainRetriever(
                domain=domain, tenant_id=tenant_id
            )
        return self._retrievers[domain_key][tenant_id]

    def search(
        self,
        domain: RAGDomain,
        query: str,
        tenant_id: str = "default",
        k: int = 3,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search a specific domain."""
        retriever = self._get_retriever(domain, tenant_id)
        results = retriever.search(query=query, k=k, filter_metadata=filter_metadata)
        logger.info(
            "[RAGManager] search domain=%s tenant=%s query='%s...' → %d results",
            domain.value, tenant_id, query[:50], len(results)
        )
        return results

    def search_all(
        self,
        query: str,
        tenant_id: str = "default",
        k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Fused search across all 5 domains, re-ranked by score."""
        all_results = []
        for domain in RAGDomain:
            try:
                results = self.search(domain, query, tenant_id=tenant_id, k=k)
                all_results.extend(results)
            except Exception as exc:
                logger.warning(
                    "[RAGManager] Domain %s search failed: %s", domain.value, exc
                )
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:k]

    def get_context(
        self,
        query: str,
        domains: Optional[List[RAGDomain]] = None,
        tenant_id: str = "default",
        k: int = 3,
        max_chars: int = 2000,
    ) -> str:
        """
        Generate a formatted context string for agent prompt injection.

        Args:
            query:    User query.
            domains:  Specific domains to search (None = all).
            tenant_id: Tenant for scoped retrieval.
            k:        Max results.
            max_chars: Max characters in context block.

        Returns:
            Formatted context string.
        """
        if domains:
            results = []
            for domain in domains:
                results.extend(self.search(domain, query, tenant_id=tenant_id, k=k))
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:k]
        else:
            results = self.search_all(query, tenant_id=tenant_id, k=k)

        if not results:
            return ""

        lines = ["--- RAG Context ---"]
        char_count = 0
        for i, r in enumerate(results, 1):
            entry = f"\n[{i}] ({r['domain']}, score={r['score']:.2f})\n{r['content']}"
            if char_count + len(entry) > max_chars:
                break
            lines.append(entry)
            char_count += len(entry)
        lines.append("\n--- End Context ---")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Domain-Specific Convenience Functions (for agents)
# ---------------------------------------------------------------------------

def search_policy_rag(query: str, tenant_id: str = "default", k: int = 3) -> str:
    """Search POLICY_RAG domain for policies, FAQs, and business rules."""
    try:
        mgr = get_rag_manager()
        results = mgr.search(RAGDomain.POLICY_RAG, query, tenant_id=tenant_id, k=k)
        if not results:
            # Fallback to legacy receptionist tools
            try:
                from tools.receptionist_rag_tools import search_receptionist_knowledge
                return search_receptionist_knowledge(query)
            except Exception:
                return "No policy information found."
        return "\n\n".join(r["content"] for r in results)
    except Exception as exc:
        logger.error("[POLICY_RAG] search failed: %s", exc)
        return f"Policy search error: {exc}"


def search_customer_rag(
    query: str,
    customer_id: Optional[str] = None,
    tenant_id: str = "default",
    k: int = 3,
) -> str:
    """Search CUSTOMER_RAG domain for customer history and preferences."""
    try:
        mgr = get_rag_manager()
        filter_meta = {"customer_id": customer_id} if customer_id else None
        results = mgr.search(
            RAGDomain.CUSTOMER_RAG, query, tenant_id=tenant_id,
            k=k, filter_metadata=filter_meta
        )
        if not results:
            try:
                from rag.retriever import search_customer_memory
                return search_customer_memory(query, customer_id=customer_id)
            except Exception:
                return "No customer history found."
        return "\n\n".join(r["content"] for r in results)
    except Exception as exc:
        logger.error("[CUSTOMER_RAG] search failed: %s", exc)
        return f"Customer RAG error: {exc}"


def search_staff_rag(
    query: str,
    staff_id: Optional[str] = None,
    tenant_id: str = "default",
    k: int = 3,
) -> str:
    """Search STAFF_RAG domain for staff performance and expertise."""
    try:
        mgr = get_rag_manager()
        filter_meta = {"staff_id": staff_id} if staff_id else None
        results = mgr.search(
            RAGDomain.STAFF_RAG, query, tenant_id=tenant_id,
            k=k, filter_metadata=filter_meta
        )
        if not results:
            try:
                from rag.retriever import search_staff_memory
                return search_staff_memory(query, staff_id=staff_id)
            except Exception:
                return "No staff information found."
        return "\n\n".join(r["content"] for r in results)
    except Exception as exc:
        logger.error("[STAFF_RAG] search failed: %s", exc)
        return f"Staff RAG error: {exc}"


def search_lead_rag(query: str, tenant_id: str = "default", k: int = 3) -> str:
    """Search LEAD_RAG domain for CRM playbooks and lead nurturing guidance."""
    try:
        mgr = get_rag_manager()
        results = mgr.search(RAGDomain.LEAD_RAG, query, tenant_id=tenant_id, k=k)
        if not results:
            try:
                from rag.retriever import search_lead_memory
                return search_lead_memory(query)
            except Exception:
                return "No lead guidance found."
        return "\n\n".join(r["content"] for r in results)
    except Exception as exc:
        logger.error("[LEAD_RAG] search failed: %s", exc)
        return f"Lead RAG error: {exc}"


def search_business_rag(query: str, tenant_id: str = "default", k: int = 3) -> str:
    """Search BUSINESS_RAG domain for historical KPI and BI context."""
    try:
        mgr = get_rag_manager()
        results = mgr.search(RAGDomain.BUSINESS_RAG, query, tenant_id=tenant_id, k=k)
        if not results:
            try:
                from rag.retriever import search_bi_memory
                return search_bi_memory(query)
            except Exception:
                return "No business intelligence history found."
        return "\n\n".join(r["content"] for r in results)
    except Exception as exc:
        logger.error("[BUSINESS_RAG] search failed: %s", exc)
        return f"Business RAG error: {exc}"


# ---------------------------------------------------------------------------
# Updated search_knowledge_base — Backward-Compatible
# ---------------------------------------------------------------------------
def search_knowledge_base_v2(
    domain: str,
    query: Optional[str] = None,
    customer_id: Optional[str] = None,
    staff_id: Optional[str] = None,
    tenant_id: str = "default",
) -> str:
    """
    Backward-compatible knowledge base search supporting both:
      - New Phase 2 domain names: POLICY_RAG, CUSTOMER_RAG, STAFF_RAG, LEAD_RAG, BUSINESS_RAG
      - Legacy domain names: policies, faq, customer_styling, lead_memory, bi_memory, etc.

    Routes to the appropriate 5-domain RAG system.
    """
    domain_upper = domain.upper().strip()
    q = query or ""

    # New Phase 2 domains
    if domain_upper == "POLICY_RAG":
        return search_policy_rag(q, tenant_id=tenant_id)
    elif domain_upper == "CUSTOMER_RAG":
        return search_customer_rag(q, customer_id=customer_id, tenant_id=tenant_id)
    elif domain_upper == "STAFF_RAG":
        return search_staff_rag(q, staff_id=staff_id, tenant_id=tenant_id)
    elif domain_upper == "LEAD_RAG":
        return search_lead_rag(q, tenant_id=tenant_id)
    elif domain_upper == "BUSINESS_RAG":
        return search_business_rag(q, tenant_id=tenant_id)

    # Legacy domain mapping
    domain_lower = domain.lower().strip()
    rag_domain = _LEGACY_DOMAIN_MAP.get(domain_lower)

    if rag_domain is None and domain_lower != "all_context":
        # Try original search_knowledge_base as ultimate fallback
        try:
            from tools.rag_unified import search_knowledge_base as _legacy_skb
            return _legacy_skb(domain=domain, query=query, customer_id=customer_id, staff_id=staff_id)
        except Exception as exc:
            return f"Error: Unknown domain '{domain}'. Phase 2 domains: POLICY_RAG, CUSTOMER_RAG, STAFF_RAG, LEAD_RAG, BUSINESS_RAG"

    if domain_lower == "all_context":
        try:
            mgr = get_rag_manager()
            ctx = mgr.get_context(q, tenant_id=tenant_id, k=4)
            return ctx if ctx else "No context found."
        except Exception as exc:
            return f"All-context search error: {exc}"

    # Map legacy → new domain
    if domain_lower in ["customer_styling", "interactions"]:
        return search_customer_rag(q, customer_id=customer_id, tenant_id=tenant_id)
    elif domain_lower in ["lead_memory", "upsell_memory", "reputation_memory"]:
        return search_lead_rag(q, tenant_id=tenant_id)
    elif domain_lower == "staff_memory":
        return search_staff_rag(q, staff_id=staff_id, tenant_id=tenant_id)
    elif domain_lower == "bi_memory":
        return search_business_rag(q, tenant_id=tenant_id)
    else:
        return search_policy_rag(q, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_rag_manager_instance: Optional[EnterpriseRAGManager] = None


def get_rag_manager() -> EnterpriseRAGManager:
    """Return the process-level EnterpriseRAGManager singleton."""
    global _rag_manager_instance
    if _rag_manager_instance is None:
        _rag_manager_instance = EnterpriseRAGManager()
        logger.info("[RAGManager] EnterpriseRAGManager singleton created.")
    return _rag_manager_instance
