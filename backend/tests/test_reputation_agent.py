"""
Unit and Integration Tests for Reputation Agent, Sentiment Analysis,
and Review Management Tools.
"""

import os
import sys
import uuid
import pytest
import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db.models import (
    Base, Branch, Service, Staff, Customer,
    Appointment, Review, AppointmentStatus, ReviewStatus,
)
from application.services.review_service import (
    fetch_reviews,
    get_review_analytics,
    detect_critical_reviews,
    generate_review_response,
    get_reputation_scorecard,
    _classify_sentiment,
    _extract_themes,
)
from ai.agents.reputation_agent import ReputationAgent, REPUTATION_SYSTEM_PROMPT
from autogen_agentchat.agents import AssistantAgent

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="reputation_db_session", scope="function")
def fixture_reputation_db_session():
    """Provides isolated, seeded SQLite memory database session for reputation tests."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    with patch("application.services.review_service.SessionLocal", return_value=db):
        try:
            # 1. Seed Branch
            branch = Branch(name="Downtown Elite", code="BR-DWTN-01", address="123 Main St", city="Metro")
            db.add(branch)
            db.commit()

            # 2. Seed Service
            srv1 = Service(name="Haircut", price=Decimal("80.00"), duration_minutes=45)
            db.add(srv1)
            db.commit()

            # 3. Seed Staff
            stylist = Staff(
                branch_id=branch.id, first_name="John", last_name="Stylist",
                email="john@salon.com", role="Stylist",
            )
            db.add(stylist)
            db.commit()

            # 4. Seed Customers
            cust1 = Customer(first_name="Alice", last_name="Smith", email="alice@gmail.com", phone="555-0001")
            cust2 = Customer(first_name="Bob", last_name="Miller", email="bob@yahoo.com", phone="555-0002")
            cust3 = Customer(first_name="Carol", last_name="Davis", email="carol@email.com", phone="555-0003")
            db.add_all([cust1, cust2, cust3])
            db.commit()

            # 5. Seed Appointments
            now = datetime.datetime.now(datetime.timezone.utc)
            appt1 = Appointment(
                customer_id=cust1.id, branch_id=branch.id, staff_id=stylist.id, service_id=srv1.id,
                start_time=now - datetime.timedelta(days=2),
                end_time=now - datetime.timedelta(days=2) + datetime.timedelta(minutes=45),
                status=AppointmentStatus.COMPLETED,
            )
            appt2 = Appointment(
                customer_id=cust2.id, branch_id=branch.id, staff_id=stylist.id, service_id=srv1.id,
                start_time=now - datetime.timedelta(days=1),
                end_time=now - datetime.timedelta(days=1) + datetime.timedelta(minutes=45),
                status=AppointmentStatus.COMPLETED,
            )
            appt3 = Appointment(
                customer_id=cust3.id, branch_id=branch.id, staff_id=stylist.id, service_id=srv1.id,
                start_time=now - datetime.timedelta(hours=6),
                end_time=now - datetime.timedelta(hours=6) + datetime.timedelta(minutes=45),
                status=AppointmentStatus.COMPLETED,
            )
            db.add_all([appt1, appt2, appt3])
            db.commit()

            # 6. Seed Reviews (mixed ratings for comprehensive testing)
            # Alice: 5-star glowing review
            rev1 = Review(
                customer_id=cust1.id, branch_id=branch.id, appointment_id=appt1.id,
                rating=5, comment="Absolutely amazing experience! Friendly staff and great results. Highly recommend!",
                status=ReviewStatus.APPROVED,
            )
            # Bob: 1-star critical review (requires escalation)
            rev2 = Review(
                customer_id=cust2.id, branch_id=branch.id, appointment_id=appt2.id,
                rating=1, comment="Terrible experience. Rude staff, had to wait forever. Never again.",
                status=ReviewStatus.PENDING,
            )
            # Carol: 3-star neutral review
            rev3 = Review(
                customer_id=cust3.id, branch_id=branch.id, appointment_id=appt3.id,
                rating=3, comment="Decent service but the wait time was a bit long. Parking was also difficult.",
                status=ReviewStatus.APPROVED,
            )
            db.add_all([rev1, rev2, rev3])
            db.commit()

            # Stash IDs for direct use in tests
            db._test_ids = {
                "branch_id": str(branch.id),
                "review_5star_id": str(rev1.id),
                "review_1star_id": str(rev2.id),
                "review_3star_id": str(rev3.id),
            }

            yield db
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# 1. Sentiment & Theme Classification Unit Tests
# ---------------------------------------------------------------------------
class TestSentimentClassification:
    """Tests for the keyword-based sentiment classifier."""

    def test_positive_from_high_rating(self):
        assert _classify_sentiment(None, 5) == "positive"
        assert _classify_sentiment("", 4) == "positive"

    def test_negative_from_low_rating(self):
        assert _classify_sentiment(None, 1) == "negative"
        assert _classify_sentiment("", 2) == "negative"

    def test_neutral_from_mid_rating(self):
        assert _classify_sentiment(None, 3) == "neutral"

    def test_keyword_override_positive(self):
        text = "The staff was amazing and the results were excellent and perfect!"
        assert _classify_sentiment(text, 3) == "positive"

    def test_keyword_override_negative(self):
        text = "Terrible experience, rude behavior, and the worst service I've had."
        assert _classify_sentiment(text, 3) == "negative"


class TestThemeExtraction:
    """Tests for the feedback theme extractor."""

    def test_no_themes_for_empty_text(self):
        assert _extract_themes(None) == []
        assert _extract_themes("") == []

    def test_detects_wait_times(self):
        themes = _extract_themes("I had to wait 30 minutes past my appointment time.")
        assert "wait times" in themes

    def test_detects_multiple_themes(self):
        themes = _extract_themes("Friendly staff and clean salon, but expensive prices.")
        assert "staff friendliness" in themes
        assert "cleanliness" in themes
        assert "pricing" in themes

    def test_detects_parking_theme(self):
        themes = _extract_themes("Great service but parking was difficult.")
        assert "parking" in themes


# ---------------------------------------------------------------------------
# 2. Database-Backed Tool Tests
# ---------------------------------------------------------------------------
class TestFetchReviews:
    """Tests for the fetch_reviews database tool."""

    def test_fetch_all_reviews(self, reputation_db_session):
        res = fetch_reviews()
        assert res["success"] is True
        assert res["total_returned"] == 3

    def test_fetch_reviews_with_min_rating(self, reputation_db_session):
        res = fetch_reviews(min_rating=4)
        assert res["success"] is True
        assert res["total_returned"] == 1
        assert res["reviews"][0]["rating"] == 5

    def test_fetch_reviews_with_max_rating(self, reputation_db_session):
        res = fetch_reviews(max_rating=2)
        assert res["success"] is True
        assert res["total_returned"] == 1
        assert res["reviews"][0]["rating"] == 1

    def test_fetch_reviews_with_status_filter(self, reputation_db_session):
        res = fetch_reviews(status="PENDING")
        assert res["success"] is True
        assert res["total_returned"] == 1
        assert res["reviews"][0]["rating"] == 1

    def test_fetch_reviews_with_invalid_status(self, reputation_db_session):
        res = fetch_reviews(status="INVALID")
        assert res["success"] is False
        assert "Invalid status" in res["error"]

    def test_reviews_contain_sentiment(self, reputation_db_session):
        res = fetch_reviews()
        assert res["success"] is True
        sentiments = {r["sentiment"] for r in res["reviews"]}
        assert "positive" in sentiments
        assert "negative" in sentiments

    def test_reviews_contain_themes(self, reputation_db_session):
        res = fetch_reviews()
        assert res["success"] is True
        # The 3-star review mentions wait times and parking
        neutral_review = next(r for r in res["reviews"] if r["rating"] == 3)
        assert "wait times" in neutral_review["themes"]
        assert "parking" in neutral_review["themes"]


class TestReviewAnalytics:
    """Tests for the get_review_analytics tool."""

    def test_analytics_returns_metrics(self, reputation_db_session):
        res = get_review_analytics()
        assert res["success"] is True
        assert res["metrics"]["total_reviews"] == 3
        assert res["metrics"]["average_rating"] == 3.0  # (5 + 1 + 3) / 3
        assert "star_distribution" in res["metrics"]

    def test_star_distribution_correct(self, reputation_db_session):
        res = get_review_analytics()
        dist = res["metrics"]["star_distribution"]
        assert dist["5"] == 1
        assert dist["1"] == 1
        assert dist["3"] == 1
        assert dist["2"] == 0
        assert dist["4"] == 0

    def test_sentiment_breakdown(self, reputation_db_session):
        res = get_review_analytics()
        sentiment = res["metrics"]["sentiment_breakdown"]
        assert sentiment["positive"] >= 1
        assert sentiment["negative"] >= 1

    def test_themes_included(self, reputation_db_session):
        res = get_review_analytics()
        assert isinstance(res["themes"], list)

    def test_chart_data_present(self, reputation_db_session):
        res = get_review_analytics()
        assert "charts" in res
        assert "rating_over_time" in res["charts"]

    def test_empty_analytics(self, reputation_db_session):
        # Query with 0-day window should return empty
        res = get_review_analytics(days=0)
        assert res["success"] is True
        assert res["metrics"]["total_reviews"] == 0


class TestCriticalReviewDetection:
    """Tests for the detect_critical_reviews tool."""

    def test_detects_critical_reviews(self, reputation_db_session):
        res = detect_critical_reviews()
        assert res["success"] is True
        assert res["total_critical"] >= 1

    def test_escalation_flag_for_1star(self, reputation_db_session):
        res = detect_critical_reviews()
        one_star = [r for r in res["critical_reviews"] if r["rating"] == 1]
        assert len(one_star) >= 1
        assert one_star[0]["requires_escalation"] is True
        assert one_star[0]["severity"] == "critical"

    def test_includes_customer_contact_info(self, reputation_db_session):
        res = detect_critical_reviews()
        assert res["success"] is True
        for review in res["critical_reviews"]:
            assert "customer_email" in review
            assert "customer_phone" in review

    def test_threshold_filtering(self, reputation_db_session):
        # Only 1-star reviews
        res = detect_critical_reviews(rating_threshold=1)
        assert res["success"] is True
        for review in res["critical_reviews"]:
            assert review["rating"] <= 1


class TestReviewResponseGeneration:
    """Tests for the generate_review_response tool."""

    def test_positive_review_response(self, reputation_db_session):
        review_id = reputation_db_session._test_ids["review_5star_id"]
        res = generate_review_response(review_id=review_id, tone="warm")
        assert res["success"] is True
        assert res["sentiment"] == "positive"
        assert res["tone_used"] == "warm"
        assert "draft_response" in res
        assert "thrilled" in res["draft_response"].lower() or "wonderful" in res["draft_response"].lower()

    def test_negative_review_response(self, reputation_db_session):
        review_id = reputation_db_session._test_ids["review_1star_id"]
        res = generate_review_response(review_id=review_id, tone="empathetic")
        assert res["success"] is True
        assert res["sentiment"] == "negative"
        assert res["tone_used"] == "empathetic"
        assert "sorry" in res["draft_response"].lower()

    def test_professional_tone(self, reputation_db_session):
        review_id = reputation_db_session._test_ids["review_3star_id"]
        res = generate_review_response(review_id=review_id, tone="professional")
        assert res["success"] is True
        assert res["tone_used"] == "professional"
        assert "draft_response" in res

    def test_invalid_tone_rejected(self, reputation_db_session):
        review_id = reputation_db_session._test_ids["review_5star_id"]
        res = generate_review_response(review_id=review_id, tone="sarcastic")
        assert res["success"] is False
        assert "Invalid tone" in res["error"]

    def test_nonexistent_review_id(self, reputation_db_session):
        fake_id = str(uuid.uuid4())
        res = generate_review_response(review_id=fake_id, tone="professional")
        assert res["success"] is False
        assert "not found" in res["error"]


class TestReputationScorecard:
    """Tests for the get_reputation_scorecard tool."""

    def test_scorecard_metrics(self, reputation_db_session):
        res = get_reputation_scorecard()
        assert res["success"] is True
        assert res["total_reviews"] == 3
        assert res["overall_rating"] == 3.0

    def test_nps_calculation(self, reputation_db_session):
        res = get_reputation_scorecard()
        # Promoters (4-5 star): 1, Detractors (1-2 star): 1 → NPS = (1-1)/3 * 100 = 0.0
        assert res["nps_estimate"] == 0.0

    def test_branch_breakdown(self, reputation_db_session):
        res = get_reputation_scorecard()
        assert len(res["branches"]) >= 1
        assert res["branches"][0]["branch_name"] == "Downtown Elite"

    def test_status_distribution(self, reputation_db_session):
        res = get_reputation_scorecard()
        assert "status_distribution" in res
        assert res["status_distribution"].get("APPROVED", 0) == 2
        assert res["status_distribution"].get("PENDING", 0) == 1


# ---------------------------------------------------------------------------
# 3. AutoGen ReputationAgent Unit Tests
# ---------------------------------------------------------------------------
class TestReputationAgentInitialization:
    """Tests for agent initialization and AutoGen configuration."""

    def test_agent_initializes(self):
        agent = ReputationAgent(name="Olivia")
        assert agent.name == "Olivia"
        assert agent.role == "Reputation & Review Manager"
        assert isinstance(agent.assistant, AssistantAgent)
        assert agent.model_client is not None

    def test_system_prompt_contains_capabilities(self):
        agent = ReputationAgent(name="Olivia")
        sys_msg = agent.assistant._system_messages[0].content
        assert "Reputation" in sys_msg
        assert "draft_review_response" in sys_msg
        assert "escalate_review" in sys_msg
        assert "mcp_read" in sys_msg

    def test_five_tools_bound(self):
        agent = ReputationAgent(name="Olivia")
        bound_tools = agent.assistant._tools
        assert len(bound_tools) == 3
        names = [t.name for t in bound_tools]
        assert "mcp_read" in names
        assert "search_knowledge_base" in names
        assert "execute_transaction" in names

    def test_analytics_initialized(self):
        agent = ReputationAgent(name="Olivia")
        analytics = agent.get_analytics()
        assert analytics["metrics"]["queries_processed"] == 0
        assert analytics["metrics"]["critical_detections"] == 0


@pytest.mark.asyncio
async def test_reputation_agent_process():
    """Verifies ReputationAgent processes queries and records session memory."""
    agent = ReputationAgent(name="Olivia")
    session_id = "rep-session-001"

    mock_result = AsyncMock()
    mock_msg = AsyncMock()
    mock_msg.content = "Found 3 critical reviews requiring immediate attention."
    mock_result.messages = [mock_msg]

    with patch.object(agent.assistant, "run", return_value=mock_result) as mock_run:
        response = await agent.process({
            "query": "Show me critical reviews from this week",
            "session_id": session_id,
        })

        assert response["success"] is True
        assert response["agent_name"] == "Olivia"
        assert response["response"] == "Found 3 critical reviews requiring immediate attention."
        assert response["session_id"] == session_id
        assert response["analytics"]["metrics"]["critical_detections"] == 1

        mock_run.assert_called_once()

        # Verify memory updated
        context = agent._get_memory_context(session_id)
        assert "User: Show me critical reviews" in context
        assert "Assistant: Found 3 critical reviews" in context


@pytest.mark.asyncio
async def test_reputation_agent_missing_query():
    """Verifies agent returns error for missing query."""
    agent = ReputationAgent(name="Olivia")
    response = await agent.process({"session_id": "test"})
    assert response["success"] is False
    assert "query" in response["error"].lower()


@pytest.mark.asyncio
async def test_reputation_agent_memory_management():
    """Verifies session memory can be cleared."""
    agent = ReputationAgent(name="Olivia")
    agent._store_memory("session-1", "user", "Hello")
    assert agent._get_memory_context("session-1") != ""

    agent.clear_memory("session-1")
    assert agent._get_memory_context("session-1") == ""

