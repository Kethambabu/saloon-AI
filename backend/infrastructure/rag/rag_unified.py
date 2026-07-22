"""
Unified RAG & Knowledge Retrieval Tool for SalonAI Workforce Platform.
Consolidates all policy checks, RAG database searches, and semantic memory lookups.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Domains that require a minimum privilege level. Mirrors mcp/permissions.py's
# ROLE_PERMISSIONS model: CUSTOMER gets booking/reputation/upsell-adjacent
# knowledge only; STAFF adds staff-facing memory; CRM (lead) and business
# intelligence stay MANAGER/OWNER/ADMIN-only, matching the intent-level RBAC
# in ai/orchestrator.py's _ROLE_ALLOWED_INTENTS. This tool is bound identically
# to all 6 agents, so without this gate a CUSTOMER-role conversation with any
# agent (e.g. Clara, Olivia) could request domain='bi_memory' or 'lead_memory'
# and retrieve business-internal data the intent router would otherwise block.
_DOMAIN_MIN_ROLES = {
    "staff_memory": {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "interactions": {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "lead_memory":  {"MANAGER", "OWNER", "ADMIN"},
    "bi_memory":    {"MANAGER", "OWNER", "ADMIN"},
    "all_context":  {"MANAGER", "OWNER", "ADMIN"},
}


def _current_role() -> str:
    """Best-effort read of the authenticated caller's role for this request."""
    try:
        from ai.orchestrator import current_user_role
        return (current_user_role.get() or "ADMIN").upper()
    except Exception:
        return "ADMIN"


def search_knowledge_base(
    domain: str,
    query: Optional[str] = None,
    customer_id: Optional[str] = None,
    staff_id: Optional[str] = None,
) -> str:
    """
    Search or retrieve documents from the SalonAI knowledge bases, policies, and semantic memory.

    Args:
        domain: The search domain. Must be one of:
            - 'policies': general salon procedures, operations, and policies
            - 'faq': client-facing FAQs
            - 'business_hours': salon operating times
            - 'cancellation_policy': appointment cancellation rules
            - 'refund_policy': payment/refund guidelines
            - 'offers': active promotional offers and discounts
            - 'customer_styling': client styling formulas and preference history
            - 'interactions': CRM client conversation and call logs
            - 'lead_memory': CRM follow-up and marketing guidelines
            - 'upsell_memory': upsell strategies and bundles guidelines
            - 'reputation_memory': review response standards and guidelines
            - 'bi_memory': corporate metrics summaries and snapshot history
            - 'staff_memory': stylist performance targets and procedures
            - 'all_context': global semantic search across all knowledge domains
        query: Semantic query text. Required for searchable domains like 'policies', 'faq', 'customer_styling', 'interactions', 'all_context', and agent memories. Optional for static documents like 'business_hours'.
        customer_id: Optional client UUID to filter styling/preference searches.
        staff_id: Optional stylist UUID to filter staff performance memory searches.
    """
    domain_lower = str(domain).strip().lower()
    q_str = str(query).strip() if query else ""

    logger.info(f"[RAGUnified] Querying knowledge base: domain='{domain_lower}', query='{q_str[:50]}'")

    required_roles = _DOMAIN_MIN_ROLES.get(domain_lower)
    if required_roles:
        role = _current_role()
        if role not in required_roles:
            logger.warning(
                "[RAGUnified] Role '%s' denied access to domain '%s' (requires one of %s)",
                role, domain_lower, sorted(required_roles),
            )
            return f"Access denied: your role does not have permission to access the '{domain_lower}' knowledge domain."

    # Try cache check
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache_ns = "policy"
        if domain_lower in ("staff_memory", "customer_styling"):
            cache_ns = "staff"
        elif domain_lower in ("bi_memory", "upsell_memory", "lead_memory", "reputation_memory"):
            cache_ns = "analytics"
            
        cache = get_cache(cache_ns)
        cached = cache.get("kb_search", domain_lower, q_str, customer_id, staff_id)
        if cached is not None:
            logger.info(f"⚡ RAG/KB cache HIT for domain='{domain_lower}' query='{q_str[:30]}'")
            return cached
    except Exception as e:
        logger.warning(f"RAG cache get failed: {e}")

    try:
        # Receptionist FAQ & Document policy lookups
        from infrastructure.rag.receptionist_rag_tools import (
            search_receptionist_knowledge,
            get_active_offers,
            get_business_timings,
            get_cancellation_policy,
            get_refund_policy,
            get_faq_answer,
        )
        # RAG / Vector db semantic memory lookups
        from infrastructure.rag.retriever import (
            search_salon_knowledge,
            search_customer_interactions,
            search_all_context,
            search_customer_memory,
            search_staff_memory,
            search_lead_memory,
            search_upsell_memory,
            search_reputation_memory,
            search_bi_memory,
        )

        res = None
        if domain_lower == "policies":
            if not q_str:
                res = "Error: Query parameter is required for policy search."
            else:
                # Prefer receptionist knowledge index for booking policy
                res = search_receptionist_knowledge(q_str)
                if "no matching" in res.lower() or len(res.strip()) < 50:
                    res = search_salon_knowledge(q_str)

        elif domain_lower == "faq":
            if not q_str:
                res = "Error: Query parameter is required for FAQ search."
            else:
                res = get_faq_answer(q_str)

        elif domain_lower == "business_hours":
            res = get_business_timings()

        elif domain_lower == "cancellation_policy":
            res = get_cancellation_policy()

        elif domain_lower == "refund_policy":
            res = get_refund_policy()

        elif domain_lower == "offers":
            res = get_active_offers()

        elif domain_lower == "customer_styling":
            if not q_str and not customer_id:
                res = "Error: Either query or customer_id is required to fetch styling preference."
            else:
                res = search_customer_memory(q_str, customer_id=customer_id)

        elif domain_lower == "interactions":
            if not q_str:
                res = "Error: Query parameter is required for client interactions lookup."
            else:
                res = search_customer_interactions(q_str)

        elif domain_lower == "lead_memory":
            if not q_str:
                res = "Error: Query parameter is required for lead memory search."
            else:
                res = search_lead_memory(q_str)

        elif domain_lower == "upsell_memory":
            if not q_str:
                res = "Error: Query parameter is required for upsell memory search."
            else:
                res = search_upsell_memory(q_str)

        elif domain_lower == "reputation_memory":
            if not q_str:
                res = "Error: Query parameter is required for reputation memory search."
            else:
                res = search_reputation_memory(q_str)

        elif domain_lower == "bi_memory":
            if not q_str:
                res = "Error: Query parameter is required for business intelligence memory search."
            else:
                res = search_bi_memory(q_str)

        elif domain_lower == "staff_memory":
            if not q_str:
                res = "Error: Query parameter is required for staff memory search."
            else:
                res = search_staff_memory(q_str, staff_id=staff_id)

        elif domain_lower == "all_context":
            if not q_str:
                res = "Error: Query parameter is required for global context search."
            else:
                res = search_all_context(q_str)

        else:
            supported = [
                "policies", "faq", "business_hours", "cancellation_policy", "refund_policy",
                "offers", "customer_styling", "interactions", "lead_memory", "upsell_memory",
                "reputation_memory", "bi_memory", "staff_memory", "all_context"
            ]
            res = f"Error: Unknown domain '{domain_lower}'. Supported domains are: {', '.join(supported)}"

        # Store in cache if successful and not an error message
        if res and not res.startswith("Error:"):
            try:
                from infrastructure.cache.token_optimizer import get_cache
                cache_ns = "policy"
                if domain_lower in ("staff_memory", "customer_styling"):
                    cache_ns = "staff"
                elif domain_lower in ("bi_memory", "upsell_memory", "lead_memory", "reputation_memory"):
                    cache_ns = "analytics"
                get_cache(cache_ns).set(res, "kb_search", domain_lower, q_str, customer_id, staff_id)
            except Exception as e:
                logger.warning(f"RAG cache set failed: {e}")

        return res

    except Exception as e:
        logger.error(f"Error in search_knowledge_base: {str(e)}", exc_info=True)
        return f"Error executing search: {str(e)}"
