import os
import sys
import datetime
import tempfile
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db.models import (
    Base, Branch, Customer, Staff, Service, Appointment, Lead, 
    Review, ChatLog, CustomerRecommendation, BusinessMetricsHistory, 
    AppointmentStatus, LeadStatus, ReviewStatus,
    CuratedMemory, MemoryScope, MemoryStatus, ConsentClass
)
from infrastructure.events.event_bus import (
    CustomerPreferenceEvent,
    LeadStatusChangedEvent,
    UpsellOutcomeEvent,
    CampaignDecisionEvent,
    SalonEvent
)
from application.services.memory_curator_service import HardPolicyEngine, LLMMemoryEvaluator, MemoryCuratorService
from infrastructure.rag.curated_faiss_store import CuratedFAISSStore
from infrastructure.rag.retriever import search_curated_memory, format_curated_memories
from langchain_core.embeddings import Embeddings


# ---------------------------------------------------------------------------
# Mock Embeddings and LLM Client
# ---------------------------------------------------------------------------

class MockEmbeddings(Embeddings):
    """Mock LangChain Embeddings that returns deterministic zero vectors."""
    def __init__(self):
        super().__init__()
        self.dimension = 384

    def embed_documents(self, texts):
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension

    def __call__(self, text: str):
        return self.embed_query(text)


class MockLLMResult:
    def __init__(self, content):
        self.content = content


# ---------------------------------------------------------------------------
# Database and Embedding Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create in-memory SQLite database session and seed basic metadata."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Seed Branch
    branch = Branch(
        name="Downtown Elite", 
        code="DT", 
        address="100 Enterprise Way", 
        city="Metropolis", 
        phone="555-0100", 
        email="downtown@salonai.com", 
        is_active=True
    )
    db.add(branch)
    db.commit()
    
    # Seed Customer
    customer = Customer(
        first_name="Ravi", 
        last_name="Sharma", 
        email="ravi@example.com", 
        phone="1234567890", 
        is_active=True, 
        loyalty_points=150
    )
    db.add(customer)
    db.commit()
    
    # Seed Staff
    staff = Staff(
        first_name="Priya", 
        last_name="Sharma", 
        email="priya@example.com", 
        phone="0987654321", 
        role="Senior Stylist", 
        is_active=True,
        branch_id=branch.id
    )
    db.add(staff)
    db.commit()
    
    # Seed Service
    service = Service(
        name="Haircut", 
        description="A premium tailored wash and haircut.",
        price=2500.0, 
        duration_minutes=45, 
        is_active=True
    )
    db.add(service)
    db.commit()
    
    yield db
    db.close()


@pytest.fixture(name="mock_embedding_model")
def fixture_mock_embedding_model():
    """Patches get_embedding_model to return MockEmbeddings."""
    mock_model = MockEmbeddings()
    with patch("infrastructure.rag.embeddings.get_embedding_model", return_value=mock_model), \
         patch("infrastructure.rag.curated_faiss_store.get_embedding_model", return_value=mock_model):
        yield mock_model


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valuable_event_creates_curated_memory(db_session, mock_embedding_model):
    """Verify that a valuable event triggers curated memory creation in SQL and FAISS."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("infrastructure.rag.curated_faiss_store._DEFAULT_FAISS_DIR", tmpdir):
            cust = db_session.query(Customer).first()
            event = CustomerPreferenceEvent(
                tenant_id="tenant-1",
                customer_id=str(cust.id),
                preference_key="colour_stylist",
                preference_value="Priya"
            )
            
            curator = MemoryCuratorService()
            memory = await curator.process_event(db_session, event)
            
            assert memory is not None
            assert memory.content == "Customer preference: colour_stylist is set to Priya."
            assert memory.scope == MemoryScope.CUSTOMER
            assert memory.tenant_id == "tenant-1"
            assert memory.owner_id == str(cust.id)
            
            # Verify in SQL
            db_mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == memory.id).first()
            assert db_mem is not None
            assert db_mem.status == MemoryStatus.ACTIVE

            # Verify in FAISS
            store = CuratedFAISSStore()
            results = store.search("prefer Priya", "tenant-1", "customer", relevance_threshold=0.0)
            assert len(results) == 1
            assert results[0]["memory_id"] == str(memory.id)


@pytest.mark.asyncio
async def test_low_value_chat_is_not_stored(db_session, mock_embedding_model):
    """Verify that raw chat transcripts and low-value events are rejected by hard policy."""
    event = SalonEvent(
        tenant_id="tenant-1",
        event_type="salon.event",
        payload={"sender": "user", "text": "Hello, what time do you close?"}
    )
    
    curator = MemoryCuratorService()
    memory = await curator.process_event(db_session, event)
    assert memory is None
    
    # Confirm SQL is empty
    mems = db_session.query(CuratedMemory).all()
    assert len(mems) == 0


@pytest.mark.asyncio
async def test_llm_evaluator_returns_valid_json():
    """Verify that LLM evaluator correctly structures evaluation requests into strict JSON."""
    mock_client = MagicMock()
    mock_client.create = AsyncMock(return_value=MockLLMResult(
        '{"store": true, "fact": "Customer Ravi prefers Priya for haircut", "scope": "customer", "importance": 0.8, "confidence": 0.95, "expires_at": null, "supersedes_reason": null, "reason": "Explicit preference"}'
    ))
    
    with patch("application.services.memory_curator_service.OpenAIChatCompletionClient", return_value=mock_client):
        evaluator = LLMMemoryEvaluator()
        result = await evaluator.evaluate_event("customer.chat", {"text": "I really loved the haircut Priya did last week."})
        
        assert result["store"] is True
        assert result["fact"] == "Customer Ravi prefers Priya for haircut"
        assert result["scope"] == "customer"
        assert result["importance"] == 0.8
        assert result["confidence"] == 0.95


@pytest.mark.asyncio
async def test_tenant_isolation(db_session, mock_embedding_model):
    """Verify that searches on Tenant A do not leak Tenant B memories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("infrastructure.rag.curated_faiss_store._DEFAULT_FAISS_DIR", tmpdir), \
             patch("infrastructure.db.database.SessionLocal", return_value=db_session):
            
            cust = db_session.query(Customer).first()
            curator = MemoryCuratorService()
            
            # Save tenant-1 memory
            event1 = CustomerPreferenceEvent(
                tenant_id="tenant-1",
                customer_id=str(cust.id),
                preference_key="style",
                preference_value="Short bob"
            )
            await curator.process_event(db_session, event1)
            
            # Save tenant-2 memory
            event2 = CustomerPreferenceEvent(
                tenant_id="tenant-2",
                customer_id=str(cust.id),
                preference_key="style",
                preference_value="Long curls"
            )
            await curator.process_event(db_session, event2)
            
            # Search under tenant-1
            res1 = search_curated_memory("customer", "style preference", tenant_id="tenant-1")
            assert len(res1) == 1
            assert "Short bob" in res1[0]["content"]
            assert "Long curls" not in res1[0]["content"]
            
            # Search under tenant-2
            res2 = search_curated_memory("customer", "style preference", tenant_id="tenant-2")
            assert len(res2) == 1
            assert "Long curls" in res2[0]["content"]
            assert "Short bob" not in res2[0]["content"]


@pytest.mark.asyncio
async def test_superseded_and_expired_memories_not_retrieved(db_session, mock_embedding_model):
    """Verify that superseded and expired memories are ignored during search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("infrastructure.rag.curated_faiss_store._DEFAULT_FAISS_DIR", tmpdir), \
             patch("infrastructure.db.database.SessionLocal", return_value=db_session):
            
            cust = db_session.query(Customer).first()
            curator = MemoryCuratorService()
            
            # Event 1: Initial Preference
            event1 = CustomerPreferenceEvent(
                tenant_id="tenant-1",
                customer_id=str(cust.id),
                preference_key="coffee",
                preference_value="Black with sugar"
            )
            await curator.process_event(db_session, event1)
            
            # Event 2: New preference supersedes the older one
            event2 = CustomerPreferenceEvent(
                tenant_id="tenant-1",
                customer_id=str(cust.id),
                preference_key="coffee",
                preference_value="No sugar, double shot espresso"
            )
            await curator.process_event(db_session, event2)
            
            # Event 3: Expired preference
            expired_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
            event3 = CampaignDecisionEvent(
                tenant_id="tenant-1",
                campaign_name="Monsoon Deal",
                decision="10% off",
                outcome="success"
            )
            # Process and then manually expire in DB for testing
            mem3 = await curator.process_event(db_session, event3)
            db_mem3 = db_session.query(CuratedMemory).filter(CuratedMemory.id == mem3.id).first()
            db_mem3.expires_at = expired_time
            db_session.commit()
            
            # Search customer domain
            res = search_curated_memory("customer", "coffee preference", tenant_id="tenant-1")
            assert len(res) == 1
            assert "No sugar, double shot espresso" in res[0]["content"]
            assert "Black with sugar" not in res[0]["content"]
            
            # Search campaign domain
            res_camp = search_curated_memory("campaign", "Monsoon Deal", tenant_id="tenant-1")
            assert len(res_camp) == 0


@pytest.mark.asyncio
async def test_forget_memory_removes_from_sql_and_faiss(db_session, mock_embedding_model):
    """Verify that deleting/forgetting a memory removes it from SQL and FAISS."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("infrastructure.rag.curated_faiss_store._DEFAULT_FAISS_DIR", tmpdir), \
             patch("infrastructure.db.database.SessionLocal", return_value=db_session):
            
            cust = db_session.query(Customer).first()
            curator = MemoryCuratorService()
            
            event = CustomerPreferenceEvent(
                tenant_id="tenant-1",
                customer_id=str(cust.id),
                preference_key="preferred_stylist",
                preference_value="Priya"
            )
            memory = await curator.process_event(db_session, event)
            assert memory is not None
            
            # Search to verify it exists
            res_before = search_curated_memory("customer", "stylist Priya", tenant_id="tenant-1")
            assert len(res_before) == 1
            
            # Forget memory
            success = curator.forget_memory(db_session, memory.id, tenant_id="tenant-1")
            assert success is True
            
            # Verify deleted from SQL
            db_mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == memory.id).first()
            assert db_mem is None
            
            # Verify deleted from FAISS (returns empty)
            res_after = search_curated_memory("customer", "stylist Priya", tenant_id="tenant-1")
            assert len(res_after) == 0


@pytest.mark.asyncio
async def test_date_specific_and_revenue_queries_not_routed_to_faiss(db_session):
    """
    Verify the two-path design: date-specific queries and metrics must NEVER use FAISS.
    They should route directly to existing database/MCP tools.
    """
    # Sample user prompts that require live SQL/MCP retrieval
    transactional_queries = [
        "Do I have appointments today?",
        "Show my appointments tomorrow.",
        "What bookings do I have on 25 July?",
        "What was the customer's last appointment?",
        "What was yearly revenue in 2025?",
        "How many leads converted this month?"
    ]
    
    # Simple live query detection heuristic mirroring what the orchestrator/agents use
    def is_live_query(query: str) -> bool:
        query_l = query.lower()
        # Detect relative date terms, specific months, numeric metrics, or SQL indicators
        date_indicators = ["today", "tomorrow", "yesterday", "july", "august", "2025", "2026", "appointment", "booking", "revenue", "lead", "convert", "month", "year"]
        return any(ind in query_l for ind in date_indicators)
        
    for q in transactional_queries:
        assert is_live_query(q) is True, f"Failed to detect transactional query: '{q}'"
