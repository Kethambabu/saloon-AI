import os
import sys
import datetime
import tempfile
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.models import (
    Base, Branch, Customer, Staff, Service, Appointment, Lead, 
    Review, ChatLog, CustomerRecommendation, BusinessMetricsHistory, 
    AppointmentStatus, LeadStatus, ReviewStatus, AgentMemory
)
from services.memory_pipeline_service import MemoryPipelineService
from tests.test_memory_pipeline import MockEmbeddings, MockLLMResult


@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create in-memory SQLite database session and seed basic metadata."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
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


@pytest.mark.asyncio
async def test_unified_sync_flow(db_session):
    """Verifies that unified incremental sync runs properly, persists summaries in DB, and sets last run date."""
    # Seed active transaction records for two days ago
    two_days_ago = datetime.date.today() - datetime.timedelta(days=2)
    day_start = datetime.datetime.combine(two_days_ago, datetime.time.min)
    
    cust = db_session.query(Customer).first()
    stf = db_session.query(Staff).first()
    svc = db_session.query(Service).first()
    brh = db_session.query(Branch).first()
    
    appt = Appointment(
        customer_id=cust.id,
        branch_id=brh.id,
        staff_id=stf.id,
        service_id=svc.id,
        start_time=day_start + datetime.timedelta(hours=10),
        end_time=day_start + datetime.timedelta(hours=10, minutes=45),
        status=AppointmentStatus.COMPLETED,
        notes="Tailored wash and haircut."
    )
    db_session.add(appt)
    
    bi_snap = BusinessMetricsHistory(
        metric_date=two_days_ago,
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
        # Patch default index directory in service to a subdirectory of tmpdir
        # so that os.path.dirname(_DEFAULT_INDEX_DIR) points to tmpdir itself, which is fresh and isolated
        faiss_dir = os.path.join(tmpdir, "faiss_indices")
        os.makedirs(faiss_dir, exist_ok=True)
        with patch("services.memory_pipeline_service._DEFAULT_INDEX_DIR", faiss_dir), \
             patch("services.memory_pipeline_service.get_embedding_model", return_value=MockEmbeddings()), \
             patch("rag.ingest.get_embedding_model", return_value=MockEmbeddings()):
            
            # Setup mock LLM completion
            from unittest.mock import AsyncMock
            mock_client = MagicMock()
            mock_client.create = AsyncMock(return_value=MockLLMResult("This is a mock LLM generated memory summary."))
            
            with patch("services.memory_pipeline_service.OpenAIChatCompletionClient", return_value=mock_client):
                service = MemoryPipelineService()
                
                # Check status initially
                status = service.get_sync_status(db_session)
                assert status["sync_available"] is True
                assert status["last_run_date"] is None
                assert status["next_sync_start"] == two_days_ago.strftime("%Y-%m-%d")
                
                # Run Unified Sync
                res = await service.run_unified_sync(db_session)
                assert res["success"] is True
                assert res["action"] == "synchronized"
                
                # Check AgentMemory DB table contains records
                db_memories = db_session.query(AgentMemory).all()
                assert len(db_memories) > 0
                
                # Check FAISS index folders exist for rebuilt daily memories
                assert os.path.exists(os.path.join(faiss_dir, "customer", "daily", "index.faiss"))
                assert os.path.exists(os.path.join(faiss_dir, "staff", "daily", "index.faiss"))
                assert os.path.exists(os.path.join(faiss_dir, "business_intelligence", "daily", "index.faiss"))
                
                # Check sync status again
                new_status = service.get_sync_status(db_session)
                assert new_status["last_run_date"] == (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                assert new_status["sync_available"] is False  # Already up to date since it synced to yesterday
                
                # Running unified sync again should return skipped action
                res_repeat = await service.run_unified_sync(db_session)
                assert res_repeat["action"] == "skipped"
                assert "already up to date" in res_repeat["message"]
