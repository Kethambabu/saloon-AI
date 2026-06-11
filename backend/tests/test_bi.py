"""
Unit and Integration Tests for Business Intelligence (BI) AI Agent and SQL protection tools.
"""

import os
import sys
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import Base, Branch, Service, Staff, Customer, Appointment, AppointmentStatus
from tools.bi_tools import (
    validate_sql_safety,
    get_revenue_analytics,
    get_staff_performance_analytics,
    get_retention_analytics,
    get_service_popularity_analytics,
    execute_bi_sql_query,
)
from agents.bi_agent import BIAgent
from autogen_agentchat.agents import AssistantAgent

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="bi_db_session", scope="function")
def fixture_bi_db_session():
    """Provides isolated, seeded SQLite memory database session for BI tests."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Patch the tools to use this mock SessionLocal
    with patch("tools.bi_tools.SessionLocal", return_value=db):
        try:
            # 1. Seed Branch
            branch = Branch(name="Downtown Elite", code="BR-DWTN-01", address="123 St", city="Metro")
            db.add(branch)
            db.commit()

            # 2. Seed Services
            srv1 = Service(name="Haircut", price=Decimal("80.00"), duration_minutes=45)
            srv2 = Service(name="Facial", price=Decimal("120.00"), duration_minutes=60)
            db.add_all([srv1, srv2])
            db.commit()

            # 3. Seed Staff
            stylist = Staff(branch_id=branch.id, first_name="John", last_name="Stylist", email="john@salon.com", role="Stylist")
            db.add(stylist)
            db.commit()

            # 4. Seed Customers
            cust1 = Customer(first_name="Alice", last_name="Smith", email="alice@gmail.com")
            cust2 = Customer(first_name="Bob", last_name="Miller", email="bob@yahoo.com")
            db.add_all([cust1, cust2])
            db.commit()

            # 5. Seed Completed Appointments
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            appt1 = Appointment(
                customer_id=cust1.id, branch_id=branch.id, staff_id=stylist.id, service_id=srv1.id,
                start_time=now - datetime.timedelta(days=1), end_time=now - datetime.timedelta(days=1, minutes=-45),
                status=AppointmentStatus.COMPLETED
            )
            # Repeat appointment for Alice to check retention
            appt2 = Appointment(
                customer_id=cust1.id, branch_id=branch.id, staff_id=stylist.id, service_id=srv2.id,
                start_time=now, end_time=now + datetime.timedelta(minutes=60),
                status=AppointmentStatus.COMPLETED
            )
            # One appointment for Bob
            appt3 = Appointment(
                customer_id=cust2.id, branch_id=branch.id, staff_id=stylist.id, service_id=srv1.id,
                start_time=now + datetime.timedelta(days=1), end_time=now + datetime.timedelta(days=1, minutes=45),
                status=AppointmentStatus.PENDING # Pending won't count as completed revenue
            )
            db.add_all([appt1, appt2, appt3])
            db.commit()

            yield db
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# 1. SQL Safety Engine Tests
# ---------------------------------------------------------------------------
def test_sql_safety_checker():
    """Verifies that validate_sql_safety prevents dangerous injections and whitelists SELECT operations."""
    # Safe queries
    is_safe, err = validate_sql_safety("SELECT * FROM staff")
    assert is_safe is True
    assert err is None

    is_safe, err = validate_sql_safety("  select first_name, last_name FROM customers JOIN appointments ON customers.id = appointments.customer_id")
    assert is_safe is True

    # SQL Injection / Mutation attempts
    is_safe, err = validate_sql_safety("INSERT INTO staff (first_name) VALUES ('Hacked')")
    assert is_safe is False
    assert "SELECT" in err

    is_safe, err = validate_sql_safety("SELECT * FROM staff; DROP TABLE customers;")
    assert is_safe is False
    assert "forbidden" in err.lower()

    is_safe, err = validate_sql_safety("SELECT * FROM staff WHERE email = 'x' OR 1=1; --'")
    assert is_safe is False

    # Unauthorized tables
    is_safe, err = validate_sql_safety("SELECT * FROM sqlite_master")
    assert is_safe is False
    assert "Access denied" in err


# ---------------------------------------------------------------------------
# 2. Database Analytics Tool Logic Tests
# ---------------------------------------------------------------------------
def test_revenue_analytics(bi_db_session):
    """Verifies that get_revenue_analytics tallies total completed revenues correctly."""
    res = get_revenue_analytics()
    assert res["success"] is True
    # Alice had completed haircut ($80) and completed facial ($120) = $200
    assert res["metrics"]["total_revenue"] == 200.0
    assert res["metrics"]["total_bookings"] == 2
    assert res["metrics"]["average_ticket"] == 100.0
    assert "charts" in res
    assert "revenue_over_time" in res["charts"]


def test_staff_performance_analytics(bi_db_session):
    """Verifies completed bookings, utilization, and ratings are benchmarking staff members correctly."""
    res = get_staff_performance_analytics()
    assert res["success"] is True
    assert len(res["staff_metrics"]) == 1
    assert res["staff_metrics"][0]["name"] == "John Stylist"
    assert res["staff_metrics"][0]["completed_bookings"] == 2
    assert res["staff_metrics"][0]["revenue_generated"] == 200.0


def test_retention_analytics(bi_db_session):
    """Verifies customer retention cohorts distinguish single visitors vs repeat bookers."""
    res = get_retention_analytics()
    assert res["success"] is True
    # Transacting customers: Alice (2 completed), Bob (0 completed, since Bob is pending)
    # So 1 transacting customer (Alice) who visited 2 times (repeat visitors = 1, LTV = $200)
    assert res["retention_metrics"]["total_transacting_customers"] == 1
    assert res["retention_metrics"]["repeat_visitors"] == 1
    assert res["retention_metrics"]["retention_rate_pct"] == 100.0
    assert res["top_customers_by_ltv"][0]["customer_name"] == "Alice Smith"
    assert res["top_customers_by_ltv"][0]["ltv"] == 200.0


def test_service_popularity_analytics(bi_db_session):
    """Verifies service volume aggregates popular items properly."""
    res = get_service_popularity_analytics()
    assert res["success"] is True
    # Haircut (1 completed), Facial (1 completed)
    assert len(res["services"]) == 2


def test_raw_sql_execution(bi_db_session):
    """Verifies raw SQL query reads work and write operations rollback."""
    # Safe execute
    res = execute_bi_sql_query("SELECT count(*) FROM staff")
    assert res["success"] is True
    assert res["row_count"] == 1
    assert res["rows"][0][0] == 1

    # Safe execute unauthorized table block
    res = execute_bi_sql_query("DELETE FROM staff")
    assert res["success"] is False
    assert "SELECT" in res["error"]


# ---------------------------------------------------------------------------
# 3. AutoGen BIAgent Unit Tests
# ---------------------------------------------------------------------------
def test_bi_agent_initialization():
    """Verifies Atlas the BI Agent initializes with correct AutoGen parameters and tools."""
    agent = BIAgent(name="Atlas")

    assert agent.name == "Atlas"
    assert agent.role == "Business Intelligence Analyst"
    assert isinstance(agent.assistant, AssistantAgent)
    assert agent.model_client is not None

    # Check prompt has whitelisted schemas
    sys_msg = agent.assistant._system_messages[0].content
    assert "branches" in sys_msg
    assert "appointments" in sys_msg
    assert "SELECT" in sys_msg

    # Check 14 BI tools are bound
    bound_tools = agent.assistant._tools
    assert len(bound_tools) == 14
    
    names = [t.name for t in bound_tools]
    assert "get_dashboard_summary" in names
    assert "get_revenue_summary" in names
    assert "get_customer_summary" in names
    assert "get_staff_summary" in names
    assert "get_lead_summary" in names
    assert "get_review_summary" in names
    assert "get_upsell_summary" in names
    assert "generate_ai_insights" in names
    assert "forecast_revenue" in names
    assert "retrieve_business_context" in names
    assert "query_raw_analytics_database" in names
    assert "trigger_returning_cohort_reminders" in names
    assert "search_salon_knowledge" in names
    assert "search_bi_memory" in names


@pytest.mark.asyncio
async def test_bi_agent_process():
    """Verifies BI agent processing pipelines queries and records history."""
    agent = BIAgent(name="Atlas")
    session_id = "bi-session"

    mock_result = AsyncMock()
    mock_msg = AsyncMock()
    mock_msg.content = "Total completed revenue for the period is $24,800."
    mock_result.messages = [mock_msg]

    with patch.object(agent.assistant, "run", return_value=mock_result) as mock_run:
        response = await agent.process({
            "query": "Show me the revenue report",
            "session_id": session_id
        })

        assert response["success"] is True
        assert response["agent_name"] == "Atlas"
        assert response["response"] == "Total completed revenue for the period is $24,800."
        assert response["session_id"] == session_id
        assert response["analytics"]["metrics"]["revenue_queries"] == 1

        mock_run.assert_called_once()
        
        # Verify memory updated
        context = agent._get_memory_context(session_id)
        assert "User: Show me the revenue report" in context
        assert "Assistant: Total completed revenue for the period" in context


def test_execute_bi_sql_query_repair():
    from tools.bi_tools import execute_bi_sql_query
    from unittest.mock import patch, MagicMock

    with patch("tools.bi_tools.SessionLocal") as mock_session_class:
        mock_db = MagicMock()
        mock_session_class.return_value = mock_db
        
        # Mock execute returning a cursor
        mock_cursor = MagicMock()
        mock_cursor.keys.return_value = ["col1"]
        mock_cursor.fetchall.return_value = [[123]]
        mock_db.execute.return_value = mock_cursor

        query = "SELECT SUM(revenue) FROM appointments WHERE start_time::date = (CURRENT_DATE - INTERVAL '2 day)'"
        res = execute_bi_sql_query(query)
        
        assert res["success"] is True
        assert res["rows"] == [[123]]
        
        # Verify db.execute was called with cleaned SQL including appended LIMIT
        called_sql = mock_db.execute.call_args[0][0].text
        expected_sql = "SELECT SUM(revenue) FROM appointments WHERE start_time::date = (CURRENT_DATE - INTERVAL '2 day') LIMIT 50"
        assert called_sql == expected_sql
