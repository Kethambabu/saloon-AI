"""
Regression coverage for application/services/entity_resolver_service.py.

Two related bugs:

1. resolve_customer() used to silently fall back to "the first active customer
   in the DB" when a supplied name/id could not be resolved, instead of raising.
   That risks operating on a real but unrelated person's data (e.g. booking or
   cancelling an appointment against the wrong customer) whenever the LLM
   passes a misspelled or nonexistent name. It must now raise ValueError
   (respecting raise_on_missing) like resolve_staff already did.

2. resolve_entity_context() ran branch/customer/staff/service resolution
   sequentially inside one try block with a single blanket except that
   returned {} on ANY failure — so one ambiguous/unresolved field (e.g. an
   ambiguous customer name) silently discarded every other already-resolved
   field (branch_id, service_id, date/time) too. Each entity is now resolved
   in its own try/except so failures are isolated and reported via
   resolved["_resolution_errors"] instead of nuking the whole result.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db import Base, Branch, Customer, Service
from application.services.entity_resolver_service import (
    resolve_customer,
    resolve_entity_context,
)

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="db_session")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_resolve_customer_raises_instead_of_falling_back_to_arbitrary_customer(db_session):
    """A nonexistent customer name must raise, not silently resolve to
    whichever customer happens to be first in the table."""
    db_session.add(Customer(first_name="Alice", last_name="Smith", email="alice@example.com"))
    db_session.commit()

    with pytest.raises(ValueError, match="Could not resolve customer"):
        resolve_customer("Totally Nonexistent Person", db_session)


def test_resolve_customer_returns_none_when_raise_on_missing_false(db_session):
    db_session.add(Customer(first_name="Alice", last_name="Smith", email="alice@example.com"))
    db_session.commit()

    assert resolve_customer("Nonexistent Person", db_session, raise_on_missing=False) is None


def test_resolve_entity_context_preserves_branch_when_customer_is_ambiguous(db_session):
    """Two customers named 'Jordan' → resolve_customer raises an ambiguous-match
    ValueError. That must not wipe out the already-resolved branch_id."""
    branch = Branch(name="Downtown", code="BR-DT-01", address="1 Main St", city="Metropolis")
    db_session.add(branch)
    db_session.add(Customer(first_name="Jordan", last_name="Lee", email="jordan.lee@example.com"))
    db_session.add(Customer(first_name="Jordan", last_name="Park", email="jordan.park@example.com"))
    db_session.commit()

    resolved = resolve_entity_context(
        {"branch_id": "Downtown", "customer_name": "Jordan"}, db=db_session
    )

    assert resolved.get("branch_id") == str(branch.id)
    assert "customer_id" not in resolved
    assert resolved.get("_resolution_errors")
    assert any("ambiguous" in e.lower() for e in resolved["_resolution_errors"])


def test_resolve_entity_context_preserves_customer_when_service_unresolvable(db_session):
    customer = Customer(first_name="Alice", last_name="Smith", email="alice2@example.com")
    db_session.add(customer)
    db_session.add(Service(name="Haircut", price=50, duration_minutes=30))
    db_session.commit()

    resolved = resolve_entity_context(
        {"customer_name": "Alice Smith", "service_name": "Nonexistent Treatment XYZ"},
        db=db_session,
    )

    # Service falls back to the default active service (existing, lower-risk
    # behavior for catalog data) rather than erroring — but customer resolution
    # must not have been discarded by any error path.
    assert resolved.get("customer_id") == str(customer.id)
