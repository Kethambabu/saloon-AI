import os
import sys

# Force testing environment variables before any other imports occur
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import types
# Dynamically map legacy modules to new paths to support unit tests unmodified
tools = types.ModuleType("tools")
sys.modules["tools"] = tools

services = types.ModuleType("services")
sys.modules["services"] = services

agents = types.ModuleType("agents")
sys.modules["agents"] = agents

rag = types.ModuleType("rag")
sys.modules["rag"] = rag

import application.services.appointment_service as app_svc
import application.services.analytics_service as anal_svc
import ai.tools.bi_tools as bi_tools
import application.services.lead_service as lead_svc
import application.services.staff_service as staff_svc
import application.services.review_service as review_svc
import application.services.loyalty_service as loyalty_svc
import ai.tools.mcp_tool as mcp_tool
import infrastructure.rag.rag_unified as rag_unified
import infrastructure.db.database as db_module
import infrastructure.rag.receptionist_rag_tools as rec_rag_tools
import application.services.receptionist_rag_service as rec_rag_svc
import application.services.memory_pipeline_service as mem_pipe_svc
import infrastructure.rag.embeddings as rag_embeddings

# Map agents
import ai.agents.receptionist_agent as rec_agent
sys.modules["agents.receptionist_agent"] = rec_agent
agents.receptionist_agent = rec_agent

import ai.orchestrator as ai_orch
sys.modules["agents.orchestrator_v3"] = ai_orch
agents.orchestrator_v3 = ai_orch

# Map rag
import infrastructure.rag.ingest as rag_ingest
import infrastructure.rag.retriever as rag_retriever
sys.modules["rag.embeddings"] = rag_embeddings
rag.embeddings = rag_embeddings
sys.modules["rag.ingest"] = rag_ingest
rag.ingest = rag_ingest
sys.modules["rag.retriever"] = rag_retriever
rag.retriever = rag_retriever

# Map routes (legacy)
routes = types.ModuleType("routes")
sys.modules["routes"] = routes
import api.routes.lead_routes as api_lead_routes
sys.modules["routes.lead_routes"] = api_lead_routes
routes.lead_routes = api_lead_routes

# Map tools
sys.modules["tools.booking_tools"] = app_svc
tools.booking_tools = app_svc

sys.modules["tools.bi_tools"] = bi_tools
tools.bi_tools = bi_tools

sys.modules["tools.lead_tools"] = lead_svc
tools.lead_tools = lead_svc

sys.modules["tools.staff_tools"] = staff_svc
tools.staff_tools = staff_svc

sys.modules["tools.reputation_tools"] = review_svc
tools.reputation_tools = review_svc

sys.modules["tools.loyalty_service"] = loyalty_svc
tools.loyalty_service = loyalty_svc

sys.modules["tools.loyalty_triggers"] = loyalty_svc
tools.loyalty_triggers = loyalty_svc

sys.modules["tools.mcp_tool"] = mcp_tool
tools.mcp_tool = mcp_tool

sys.modules["tools.rag_unified"] = rag_unified
tools.rag_unified = rag_unified

sys.modules["tools.transaction_unified"] = db_module
tools.transaction_unified = db_module

sys.modules["tools.receptionist_rag_tools"] = rec_rag_tools
tools.receptionist_rag_tools = rec_rag_tools

# Map services
import application.services.entity_resolver_service as entity_resolver
import application.services.conversation_state_service as conv_state
import application.services.permission_guard as perm_guard
import application.services.enterprise_permission as ent_perm

sys.modules["services.entity_resolver_service"] = entity_resolver
services.entity_resolver_service = entity_resolver

sys.modules["services.conversation_state_service"] = conv_state
services.conversation_state_service = conv_state

sys.modules["services.permission_guard"] = perm_guard
services.permission_guard = perm_guard

sys.modules["services.enterprise_permission"] = ent_perm
services.enterprise_permission = ent_perm

sys.modules["services.lead_service"] = lead_svc
services.lead_service = lead_svc

sys.modules["services.analytics_service"] = anal_svc
services.analytics_service = anal_svc

sys.modules["services.receptionist_rag_service"] = rec_rag_svc
services.receptionist_rag_service = rec_rag_svc

sys.modules["services.memory_pipeline_service"] = mem_pipe_svc
services.memory_pipeline_service = mem_pipe_svc





import pytest
from fastapi.testclient import TestClient

from main import create_app
from core.config import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings"""
    return Settings(
        environment="testing",
        database_url="sqlite:///./test.db",
        debug=True,
    )


@pytest.fixture(scope="session")
def app(test_settings):
    """Create test app"""
    return create_app(settings=test_settings)


@pytest.fixture(scope="session")
def client(app):
    """Create test client"""
    with TestClient(app) as c:
        yield c



@pytest.fixture(autouse=True)
def reset_cooldowns():
    """Reset model cooldowns before each test to prevent cross-test pollution."""
    try:
        from ai.agents.receptionist_agent import ReceptionistAgent
        ReceptionistAgent.MODEL_COOLDOWN = {}
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def clean_database():
    """Clean the test SQLite database sessions, appointments, and chat logs before each test to prevent cross-test state leakage."""
    try:
        from infrastructure.db.database import SessionLocal
        from infrastructure.db.models import ConversationSession, Appointment, ChatLog
        db = SessionLocal()
        try:
            db.query(ConversationSession).delete()
            db.query(Appointment).delete()
            db.query(ChatLog).delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass


__all__ = ["test_settings", "app", "client"]


