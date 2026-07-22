import os
import sys
import datetime
import tempfile
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db.models import (
    Base, Branch, Customer, Staff, Service, Appointment, Lead, 
    Review, ChatLog, CustomerRecommendation, BusinessMetricsHistory, 
    AppointmentStatus, LeadStatus, ReviewStatus, AgentMemory
)
from application.services.memory_pipeline_service import MemoryPipelineService
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
    """
    MemoryPipelineService (the old daily/weekly/monthly/yearly hierarchical
    roll-up pipeline) is deliberately deprecated and retired — replaced by
    the event-driven MemoryCuratorService (see KETHAM_ARCHITECTURE.md,
    application/services/memory_pipeline_service.py). This test previously
    exercised the pre-deprecation behavior (expecting run_unified_sync to
    actually build FAISS indices) and had gone stale, failing against the
    service's real, intentional contract. It now verifies that contract:
    every roll-up entry point raises DeprecatedError and get_sync_status
    reports the deprecated state — mirroring tests/test_memory_pipeline.py.
    """
    # Seed a minimal active transaction record so the fixture data is used
    # (kept for parity with the DB schema the service still type-checks against).
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
    db_session.commit()

    from application.services.memory_pipeline_service import DeprecatedError

    service = MemoryPipelineService()

    status = service.get_sync_status(db_session)
    assert status["deprecated"] is True
    assert status["sync_available"] is False

    with pytest.raises(DeprecatedError):
        await service.run_unified_sync(db_session)

    with pytest.raises(DeprecatedError):
        await service.run_daily_pipeline(db_session, target_date=two_days_ago)

    with pytest.raises(DeprecatedError):
        await service.run_weekly_pipeline(db_session, end_date=two_days_ago)

    with pytest.raises(DeprecatedError):
        await service.run_monthly_pipeline(db_session, end_date=two_days_ago)

    with pytest.raises(DeprecatedError):
        await service.run_yearly_pipeline(db_session, year=two_days_ago.year)

    # No AgentMemory rows should be created by a deprecated no-op pipeline.
    assert db_session.query(AgentMemory).count() == 0

