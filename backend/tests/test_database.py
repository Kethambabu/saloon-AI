"""
Unit and Integration Tests for Database Layer.
Verifies UUID generation, relationships, cascade behaviors, constraints,
and transaction rollback mechanisms.
"""

import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, DataError

from db import (
    Base,
    Branch,
    Staff,
    Customer,
    Service,
    Appointment,
    Lead,
    Review,
    AppointmentStatus,
    LeadStatus,
    ReviewStatus,
    check_db_health,
)

# Test-specific SQLite memory database engine
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    """Provides a clean, isolated in-memory SQLite database session for each test case."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_database_health():
    """Verifies that the database connection health check functions correctly."""
    assert check_db_health() is True


def test_uuid_primary_keys_and_timestamps(db_session):
    """Verifies that inserting a record auto-generates a UUID primary key and timezone-aware timestamps."""
    new_branch = Branch(
        name="Luxe Downtown",
        code="BR-LUXE-01",
        address="123 Main St",
        city="Metropolis"
    )
    db_session.add(new_branch)
    db_session.commit()

    assert new_branch.id is not None
    # Verify primary key is a valid UUID
    import uuid
    assert isinstance(new_branch.id, uuid.UUID)
    assert new_branch.created_at is not None
    assert new_branch.updated_at is not None


def test_relationships_and_cascades(db_session):
    """Verifies that foreign key relationships are enforced and branch cascades delete linked staff and appointments."""
    # 1. Setup Branch
    branch = Branch(name="Cascading Oasis", code="BR-CASC-01", address="456 Hill Rd", city="Metropolis")
    db_session.add(branch)
    db_session.commit()

    # 2. Add Service
    service = Service(name="Trim", price=Decimal("40.00"), duration_minutes=30)
    db_session.add(service)

    # 3. Add Customer
    customer = Customer(first_name="Jane", last_name="Doe", email="jane.doe@example.com")
    db_session.add(customer)
    db_session.commit()

    # 4. Add Staff linked to Branch
    staff = Staff(
        branch_id=branch.id,
        first_name="Jack",
        last_name="Stylist",
        email="jack@stylist.com",
        role="Stylist"
    )
    db_session.add(staff)
    db_session.commit()

    # 5. Add Appointment linked to Branch, Customer, Staff, Service
    now = datetime.now(timezone.utc)
    appointment = Appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        staff_id=staff.id,
        service_id=service.id,
        start_time=now,
        end_time=now + timedelta(minutes=30),
        status=AppointmentStatus.PENDING
    )
    db_session.add(appointment)
    db_session.commit()

    # Verify counts before deletion
    assert db_session.query(Staff).count() == 1
    assert db_session.query(Appointment).count() == 1

    # Delete Branch and verify cascades
    db_session.delete(branch)
    db_session.commit()

    # Staff and Appointments should be cascade deleted because their relationship specifies CASCADE
    assert db_session.query(Staff).count() == 0
    assert db_session.query(Appointment).count() == 0

    # Customers and Services should remain untouched
    assert db_session.query(Customer).count() == 1
    assert db_session.query(Service).count() == 1


def test_rating_range_check_constraint(db_session):
    """Verifies that reviews enforce rating values between 1 and 5 (enforced by database check constraint)."""
    branch = Branch(name="Review Spot", code="BR-REV-01", address="789 Lane St", city="Metropolis")
    customer = Customer(first_name="John", last_name="Reviewer", email="john@reviewer.com")
    db_session.add_all([branch, customer])
    db_session.commit()

    # Inserting invalid rating (rating 6)
    invalid_review = Review(
        customer_id=customer.id,
        branch_id=branch.id,
        rating=6,  # Invalid! Out of 1-5 range.
        comment="Too high score!",
        status=ReviewStatus.PENDING
    )
    db_session.add(invalid_review)
    
    # Commit must fail due to check constraint
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_transaction_rollback_behavior(db_session):
    """Verifies that database failures roll back the entire active transaction block to keep data consistent."""
    branch = Branch(name="Rollback Branch", code="BR-ROLL-01", address="Rollback Rd", city="Metropolis")
    db_session.add(branch)
    db_session.commit()

    # Start a transaction block
    try:
        # Add a valid staff
        staff_good = Staff(
            branch_id=branch.id,
            first_name="Good",
            last_name="Worker",
            email="good@salon.com",
            role="Stylist"
        )
        db_session.add(staff_good)

        # Add an invalid staff missing required non-nullable fields (e.g. email=None)
        staff_bad = Staff(
            branch_id=branch.id,
            first_name="Bad",
            last_name="Worker",
            email=None,  # Invalid! Not nullable in DB.
            role="Stylist"
        )
        db_session.add(staff_bad)
        
        # Flush or commit will trigger an IntegrityError
        db_session.commit()
    except IntegrityError:
        db_session.rollback()

    # The entire transaction block must have rolled back. Good worker should NOT be in the DB.
    assert db_session.query(Staff).filter_by(first_name="Good").count() == 0


def test_enums_serialization(db_session):
    """Verifies that enums serialize correctly to and from database records."""
    branch = Branch(name="Lead Hub", code="BR-LEAD-01", address="101 Lead Way", city="Metropolis")
    db_session.add(branch)
    db_session.commit()

    new_lead = Lead(
        branch_id=branch.id,
        first_name="Bob",
        last_name="Inquirer",
        email="bob@inquirer.com",
        source="website",
        status=LeadStatus.CONTACTED,
        notes="Interested in membership."
    )
    db_session.add(new_lead)
    db_session.commit()

    # Retrieve lead and check enum parsing
    retrieved = db_session.query(Lead).filter_by(first_name="Bob").first()
    assert retrieved is not None
    assert retrieved.status == LeadStatus.CONTACTED
    assert isinstance(retrieved.status, LeadStatus)
