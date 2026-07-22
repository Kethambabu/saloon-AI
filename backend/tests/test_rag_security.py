"""
Validation tests for the RAG security/tenant fixes:

1. search_knowledge_base role-gates sensitive domains (bi_memory, lead_memory,
   staff_memory, interactions, all_context) so a CUSTOMER-role conversation
   with any agent cannot pull business-internal or cross-customer data.
2. search_customer_memory force-overrides an explicitly supplied customer_id
   to the caller's own identity when the caller is a CUSTOMER, mirroring
   mcp/query_guard.py's handling of customer_id for DB queries.
3. search_upsell_memory scopes results to the caller's own customer memory
   (and drops cross-lead CRM data) when the caller is a CUSTOMER.
4. The orchestrator's RAG prompt-context injection uses the per-request
   tenant (current_tenant_id_var), not the orchestrator singleton's
   constructor-time tenant_id.
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ai.orchestrator as orch
from infrastructure.rag import rag_unified
from infrastructure.rag import retriever
from infrastructure.rag import enterprise_rag
from infrastructure.rag.enterprise_rag import RAGDomain


def _set_role(role):
    token = orch.current_user_role.set(role)
    return token


# ---------------------------------------------------------------------------
# 1. Domain role gating in search_knowledge_base
# ---------------------------------------------------------------------------
def test_customer_blocked_from_bi_memory():
    token = _set_role("CUSTOMER")
    try:
        result = rag_unified.search_knowledge_base(domain="bi_memory", query="revenue trends")
        assert result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_customer_blocked_from_lead_memory():
    token = _set_role("CUSTOMER")
    try:
        result = rag_unified.search_knowledge_base(domain="lead_memory", query="pipeline")
        assert result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_customer_blocked_from_staff_memory():
    token = _set_role("CUSTOMER")
    try:
        result = rag_unified.search_knowledge_base(domain="staff_memory", query="performance")
        assert result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_customer_blocked_from_interactions():
    token = _set_role("CUSTOMER")
    try:
        result = rag_unified.search_knowledge_base(domain="interactions", query="other appointments")
        assert result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_customer_blocked_from_all_context():
    token = _set_role("CUSTOMER")
    try:
        result = rag_unified.search_knowledge_base(domain="all_context", query="everything")
        assert result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_staff_blocked_from_bi_memory_and_lead_memory():
    token = _set_role("STAFF")
    try:
        assert rag_unified.search_knowledge_base(domain="bi_memory", query="x").startswith("Access denied")
        assert rag_unified.search_knowledge_base(domain="lead_memory", query="x").startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_staff_allowed_staff_memory_domain_not_blocked_by_role_gate():
    # STAFF is in the staff_memory allow-list; downstream check_staff_access
    # (not exercised here) still governs whose staff record can be viewed.
    token = _set_role("STAFF")
    try:
        result = rag_unified.search_knowledge_base(domain="staff_memory", query="x")
        assert not result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_manager_allowed_bi_memory():
    token = _set_role("MANAGER")
    try:
        result = rag_unified.search_knowledge_base(domain="bi_memory", query="revenue")
        assert not result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


def test_customer_still_allowed_policy_domains():
    token = _set_role("CUSTOMER")
    try:
        result = rag_unified.search_knowledge_base(domain="business_hours")
        assert not result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(token)


# ---------------------------------------------------------------------------
# 2. Customer-id ownership enforcement in search_customer_memory
# ---------------------------------------------------------------------------
def test_customer_cannot_read_other_customers_memory_via_explicit_id():
    role_token = _set_role("CUSTOMER")
    try:
        with patch(
            "application.services.entity_resolver_service._get_context_customer_id",
            return_value="own-customer-id",
        ), patch(
            "infrastructure.rag.retriever.search_curated_memory",
            return_value=[],
        ) as mock_search:
            retriever.search_customer_memory("allergy info", customer_id="someone-elses-id")
            # Must have been called with the CALLER's own id, not the requested one
            _, kwargs = mock_search.call_args
            assert kwargs["owner_id"] == "own-customer-id"
    finally:
        orch.current_user_role.reset(role_token)


def test_customer_denied_when_own_identity_unresolvable():
    role_token = _set_role("CUSTOMER")
    try:
        with patch(
            "application.services.entity_resolver_service._get_context_customer_id",
            return_value=None,
        ):
            result = retriever.search_customer_memory("allergy info", customer_id="someone-elses-id")
            assert result.startswith("Access denied")
    finally:
        orch.current_user_role.reset(role_token)


def test_staff_can_still_query_explicit_customer_id():
    role_token = _set_role("STAFF")
    try:
        with patch(
            "infrastructure.rag.retriever.search_curated_memory",
            return_value=[],
        ) as mock_search:
            retriever.search_customer_memory("allergy info", customer_id="12345678-1234-1234-1234-123456789012")
            _, kwargs = mock_search.call_args
            assert kwargs["owner_id"] == "12345678-1234-1234-1234-123456789012"
    finally:
        orch.current_user_role.reset(role_token)


# ---------------------------------------------------------------------------
# 3. Upsell memory scoping for CUSTOMER role
# ---------------------------------------------------------------------------
def test_customer_upsell_memory_excludes_lead_data():
    role_token = _set_role("CUSTOMER")
    try:
        with patch(
            "application.services.entity_resolver_service._get_context_customer_id",
            return_value="own-customer-id",
        ), patch(
            "infrastructure.rag.retriever.search_curated_memory",
            return_value=[],
        ) as mock_search:
            retriever.search_upsell_memory("bundle discount")
            # Only ever called once, for "customer" domain scoped to the caller
            assert mock_search.call_count == 1
            args, kwargs = mock_search.call_args
            assert args[0] == "customer"
            assert kwargs["owner_id"] == "own-customer-id"
    finally:
        orch.current_user_role.reset(role_token)


def test_staff_upsell_memory_still_sees_lead_data():
    role_token = _set_role("STAFF")
    try:
        with patch(
            "infrastructure.rag.retriever.search_curated_memory",
            return_value=[],
        ) as mock_search:
            retriever.search_upsell_memory("bundle discount")
            called_domains = [c.args[0] for c in mock_search.call_args_list]
            assert "customer" in called_domains
            assert "lead" in called_domains
    finally:
        orch.current_user_role.reset(role_token)


# ---------------------------------------------------------------------------
# 4. Orchestrator RAG context uses per-request tenant, not the singleton's
# ---------------------------------------------------------------------------
def test_build_enriched_query_uses_request_tenant_not_instance_tenant():
    fake_self = SimpleNamespace(tenant_id="default", _budget_enforcer=None)

    session_state = SimpleNamespace(
        pending_booking=None,
        user_role="CUSTOMER",
        metadata={},
        build_context_string=lambda n=6: "",
    )

    fake_settings = SimpleNamespace(is_testing=False)
    tenant_token = orch.current_tenant_id_var.set("tenant-xyz")
    try:
        with patch("ai.orchestrator.get_settings", return_value=fake_settings), \
             patch("infrastructure.rag.enterprise_rag.get_rag_manager") as mock_get_mgr:
            mock_mgr = mock_get_mgr.return_value
            mock_mgr.get_context.return_value = ""

            orch.MultiAgentOrchestrator._build_enriched_query(
                fake_self,
                query="What are your hours?",
                session_state=session_state,
                entity_context={},
                intent=orch.AgentIntent.BOOKING,
            )

            assert mock_mgr.get_context.called
            _, kwargs = mock_mgr.get_context.call_args
            assert kwargs["tenant_id"] == "tenant-xyz"
    finally:
        orch.current_tenant_id_var.reset(tenant_token)


# ---------------------------------------------------------------------------
# 5. search_customer_interactions: STAFF excludes leads, CUSTOMER self-scoped
# ---------------------------------------------------------------------------
def test_staff_interactions_search_excludes_lead_docs():
    role_token = _set_role("STAFF")
    try:
        fake_results = [
            {"content": "appt", "score": 0.9, "metadata": {"doc_type": "appointment"}},
            {"content": "review", "score": 0.8, "metadata": {"doc_type": "review"}},
            {"content": "lead", "score": 0.7, "metadata": {"doc_type": "lead"}},
        ]
        with patch("infrastructure.rag.retriever.get_retriever") as mock_get_retriever:
            mock_get_retriever.return_value.search_interactions.return_value = fake_results
            result_str = retriever.search_customer_interactions("Alice history")
            result = eval(result_str)
            doc_types = [r["metadata"]["doc_type"] for r in result["results"]]
            assert "lead" not in doc_types
            assert "appointment" in doc_types
            assert "review" in doc_types
    finally:
        orch.current_user_role.reset(role_token)


def test_manager_interactions_search_keeps_lead_docs():
    role_token = _set_role("MANAGER")
    try:
        fake_results = [
            {"content": "lead", "score": 0.7, "metadata": {"doc_type": "lead"}},
        ]
        with patch("infrastructure.rag.retriever.get_retriever") as mock_get_retriever:
            mock_get_retriever.return_value.search_interactions.return_value = fake_results
            result_str = retriever.search_customer_interactions("pipeline")
            result = eval(result_str)
            assert result["total"] == 1
    finally:
        orch.current_user_role.reset(role_token)


def test_customer_interactions_search_scoped_to_own_id():
    role_token = _set_role("CUSTOMER")
    try:
        fake_results = [
            {"content": "own appt", "score": 0.9, "metadata": {"doc_type": "appointment", "customer_id": "own-id"}},
            {"content": "other appt", "score": 0.9, "metadata": {"doc_type": "appointment", "customer_id": "other-id"}},
        ]
        with patch("infrastructure.rag.retriever.get_retriever") as mock_get_retriever, \
             patch("application.services.entity_resolver_service._get_context_customer_id", return_value="own-id"):
            mock_get_retriever.return_value.search_interactions.return_value = fake_results
            result_str = retriever.search_customer_interactions("my appointments")
            result = eval(result_str)
            assert result["total"] == 1
            assert result["results"][0]["metadata"]["customer_id"] == "own-id"
    finally:
        orch.current_user_role.reset(role_token)


# ---------------------------------------------------------------------------
# 6. search_reputation_memory owner scoping for CUSTOMER
# ---------------------------------------------------------------------------
def test_customer_reputation_memory_scoped_to_own_id():
    role_token = _set_role("CUSTOMER")
    try:
        with patch(
            "application.services.entity_resolver_service._get_context_customer_id",
            return_value="own-customer-id",
        ), patch(
            "infrastructure.rag.retriever.search_curated_memory",
            return_value=[],
        ) as mock_search:
            retriever.search_reputation_memory("service complaint")
            args, kwargs = mock_search.call_args
            assert args[0] == "reputation"
            assert kwargs["owner_id"] == "own-customer-id"
    finally:
        orch.current_user_role.reset(role_token)


def test_staff_reputation_memory_unscoped():
    role_token = _set_role("STAFF")
    try:
        with patch(
            "infrastructure.rag.retriever.search_curated_memory",
            return_value=[],
        ) as mock_search:
            retriever.search_reputation_memory("service complaint")
            args, kwargs = mock_search.call_args
            assert args[0] == "reputation"
            assert "owner_id" not in kwargs
    finally:
        orch.current_user_role.reset(role_token)


# ---------------------------------------------------------------------------
# 7. enterprise_rag.py hardening (dormant API, defense-in-depth)
# ---------------------------------------------------------------------------
def test_enterprise_rag_manager_denies_lead_and_business_domains_for_customer():
    role_token = _set_role("CUSTOMER")
    try:
        mgr = enterprise_rag.EnterpriseRAGManager()
        with patch.object(mgr, "_get_retriever") as mock_get_retriever:
            results = mgr.search(RAGDomain.LEAD_RAG, "objections")
            assert results == []
            results = mgr.search(RAGDomain.BUSINESS_RAG, "revenue")
            assert results == []
            # Retriever should never even be constructed for a denied domain
            mock_get_retriever.assert_not_called()
    finally:
        orch.current_user_role.reset(role_token)


def test_enterprise_rag_manager_allows_manager_business_domain():
    role_token = _set_role("MANAGER")
    try:
        mgr = enterprise_rag.EnterpriseRAGManager()
        with patch.object(mgr, "_get_retriever") as mock_get_retriever:
            mock_get_retriever.return_value.search.return_value = []
            mgr.search(RAGDomain.BUSINESS_RAG, "revenue")
            mock_get_retriever.assert_called_once()
    finally:
        orch.current_user_role.reset(role_token)


def test_search_customer_rag_overrides_foreign_customer_id():
    role_token = _set_role("CUSTOMER")
    try:
        with patch(
            "application.services.entity_resolver_service._get_context_customer_id",
            return_value="own-id",
        ), patch("infrastructure.rag.enterprise_rag.get_rag_manager") as mock_get_mgr:
            mock_mgr = mock_get_mgr.return_value
            mock_mgr.search.return_value = []
            with patch("infrastructure.rag.retriever.search_customer_memory", return_value="fallback"):
                enterprise_rag.search_customer_rag("styling", customer_id="someone-elses-id")
            _, kwargs = mock_mgr.search.call_args
            assert kwargs["filter_metadata"] == {"customer_id": "own-id"}
    finally:
        orch.current_user_role.reset(role_token)


def test_search_staff_rag_denies_cross_staff_lookup():
    role_token = _set_role("STAFF")
    try:
        with patch("core.query_context.check_staff_access", return_value="Access denied. You do not have permission to view details of other staff members."):
            result = enterprise_rag.search_staff_rag("performance", staff_id="12345678-1234-1234-1234-123456789012")
            assert "Access denied" in result
    finally:
        orch.current_user_role.reset(role_token)
