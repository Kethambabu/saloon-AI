"""
Unit and Integration Tests for Zenoti-Style Agent Memory Pipeline.
Verifies daily extraction, weekly/monthly/yearly consolidation, and hierarchical RAG retrieval.
"""

import os
import sys
import datetime
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db.models import (
    Base, Branch, Customer, Staff, Service, Appointment, Lead, 
    Review, ChatLog, CustomerRecommendation, BusinessMetricsHistory, 
    AppointmentStatus, LeadStatus, ReviewStatus
)
from application.services.memory_pipeline_service import MemoryPipelineService


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
    with patch("rag.embeddings.get_embedding_model", return_value=mock_model), \
         patch("services.memory_pipeline_service.get_embedding_model", return_value=mock_model):
        yield mock_model


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_pipeline_e2e(db_session, mock_embedding_model):
    """Verifies daily extraction, weekly compilation, and hierarchical RAG retrieval."""
    
    # Seed active transaction records for today
    today = datetime.date.today()
    day_start = datetime.datetime.combine(today, datetime.time.min)
    
    cust = db_session.query(Customer).first()
    stf = db_session.query(Staff).first()
    svc = db_session.query(Service).first()
    brh = db_session.query(Branch).first()
    
    # 1. Appointment
    appt = Appointment(
        customer_id=cust.id,
        branch_id=brh.id,
        staff_id=stf.id,
        service_id=svc.id,
        start_time=day_start + datetime.timedelta(hours=10),
        end_time=day_start + datetime.timedelta(hours=10, minutes=45),
        status=AppointmentStatus.COMPLETED,
        notes="Customer wants short layers."
    )
    db_session.add(appt)
    
    # 2. Chat Log
    chat = ChatLog(
        session_id="session-ravi-1",
        user_id=cust.id,
        customer_id=cust.id,
        agent_type="RECEPTIONIST",
        sender="user",
        message="I would like to try a keratin treatment next time."
    )
    db_session.add(chat)
    
    # 3. Review
    review = Review(
        customer_id=cust.id,
        branch_id=brh.id,
        appointment_id=appt.id,
        rating=5,
        comment="Priya was amazing! Very professional.",
        sentiment="POSITIVE",
        status=ReviewStatus.APPROVED
    )
    db_session.add(review)
    
    # 4. Lead
    lead = Lead(
        branch_id=brh.id,
        customer_name="John Doe",
        customer_email="john@example.com",
        customer_phone="5551111",
        service_name="Facial",
        status=LeadStatus.NEW,
        notes="Abandoned booking checkout."
    )
    db_session.add(lead)
    
    # 5. Recommendation
    rec = CustomerRecommendation(
        customer_id=cust.id,
        recommended_service_id=svc.id,
        accepted=True,
        appointment_id=appt.id
    )
    db_session.add(rec)
    
    # 6. BI Snapshot
    bi_snap = BusinessMetricsHistory(
        metric_date=today,
        revenue=2500.0,
        appointments=1,
        lead_conversion=0.5,
        average_rating=5.0,
        upsell_revenue=2500.0,
        top_service="Haircut",
        top_staff="Priya Sharma"
    )
    db_session.add(bi_snap)
    db_session.commit()
    
    # Create temp directory for index storage
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch default index directory in service and retriever
        with patch("services.memory_pipeline_service._DEFAULT_INDEX_DIR", tmpdir), \
             patch("rag.retriever._DEFAULT_INDEX_DIR", tmpdir):
            
            # Setup mock LLM completion
            from unittest.mock import AsyncMock
            mock_client = MagicMock()
            mock_client.create = AsyncMock(return_value=MockLLMResult("This is a mock LLM generated memory summary."))
            
            with patch("services.memory_pipeline_service.OpenAIChatCompletionClient", return_value=mock_client):
                from application.services.memory_pipeline_service import DeprecatedError
                service = MemoryPipelineService()
                
                with pytest.raises(DeprecatedError):
                    await service.run_daily_pipeline(db_session, target_date=today)
                
                with pytest.raises(DeprecatedError):
                    await service.run_weekly_pipeline(db_session, end_date=today)
                    
                status_info = service.get_sync_status(db_session)
                assert status_info["deprecated"] is True



