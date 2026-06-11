import os
import sys
import datetime
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.models import Base, KnowledgeDocument, SpecialOffer, User, UserRole
from services.receptionist_rag_service import ReceptionistRAGService
from tools.receptionist_rag_tools import (
    search_receptionist_knowledge,
    get_active_offers,
    get_business_timings,
    get_cancellation_policy,
    get_refund_policy,
    get_faq_answer,
)
from main import create_app
from core.config import Settings
from langchain_core.embeddings import Embeddings


# ---------------------------------------------------------------------------
# Mock Embeddings
# ---------------------------------------------------------------------------

class MockEmbeddings(Embeddings):
    """Mock LangChain Embeddings that returns deterministic zero vectors."""
    def __init__(self):
        super().__init__()
        self.dimension = 3072

    def embed_documents(self, texts):
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension

    def __call__(self, text: str):
        return self.embed_query(text)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="db_session")
def fixture_db_session():
    """Create in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    # Mock close to prevent helper tools/endpoints from closing and detaching objects
    real_close = db.close
    db.close = lambda: None
    yield db
    db.close = real_close
    db.close()


@pytest.fixture(name="mock_embedding_model")
def fixture_mock_embedding_model():
    """Patches get_embedding_model to return MockEmbeddings."""
    mock_model = MockEmbeddings()
    with patch("rag.embeddings.get_embedding_model", return_value=mock_model), \
         patch("services.receptionist_rag_service.get_embedding_model", return_value=mock_model), \
         patch("tools.receptionist_rag_tools.get_embedding_model", return_value=mock_model):
        yield mock_model


# ---------------------------------------------------------------------------
# Ingestion and Tools Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_receptionist_rag_service_and_tools(db_session, mock_embedding_model):
    """Tests the document and offer ingestion pipeline and the retriever tools."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the local index directory paths
        with patch("services.receptionist_rag_service._RECEPTIONIST_KNOWLEDGE_DIR", tmpdir), \
             patch("tools.receptionist_rag_tools._RECEPTIONIST_KNOWLEDGE_DIR", tmpdir), \
             patch("tools.receptionist_rag_tools.SessionLocal", return_value=db_session):
            
            service = ReceptionistRAGService()

            # 1. Upload Cancellation Policy V1 (Plain text)
            policy_text_1 = "Appointments must be cancelled at least 24 hours in advance to avoid a fee."
            doc1 = service.upload_policy_document(
                db=db_session,
                title="Cancellation Policy V1",
                doc_type="cancellation_policy",
                file_bytes=policy_text_1.encode("utf-8"),
                file_name="cancel_v1.txt"
            )
            assert doc1.version == 1
            assert doc1.is_active is True
            assert os.path.exists(os.path.join(tmpdir, "index.faiss"))

            # Check direct timing query before upload
            timing_res = get_business_timings()
            assert "not configured" in timing_res

            # 2. Upload Timings Policy V1
            timings_text = "Salon opens from 9 AM to 8 PM daily."
            doc2 = service.upload_policy_document(
                db=db_session,
                title="Business Hours",
                doc_type="timings",
                file_bytes=timings_text.encode("utf-8"),
                file_name="timings.txt"
            )
            assert doc2.version == 1
            assert get_business_timings() == f"--- Active Business Hours (Version: 1) ---\n{timings_text}"

            # 3. Upload Cancellation Policy V2 (representing an update)
            policy_text_2 = "Cancellation is required before 12 hours. Late cancels charge 30%."
            doc3 = service.upload_policy_document(
                db=db_session,
                title="Cancellation Policy V2",
                doc_type="cancellation_policy",
                file_bytes=policy_text_2.encode("utf-8"),
                file_name="cancel_v2.txt"
            )
            assert doc3.version == 2
            assert doc3.is_active is True
            
            # Verify V1 is deactivated
            db_session.refresh(doc1)
            assert doc1.is_active is False

            # Verify direct cancellation query returns V2 policy
            assert get_cancellation_policy() == f"--- Active Cancellation Policy V2 (Version: 2) ---\n{policy_text_2}"

            # 4. Create active special offer
            today = datetime.date.today()
            offer = service.create_special_offer(
                db=db_session,
                title="Grand Opening Discount",
                description="Get 20% off all styling and spa treatments.",
                discount_pct=20.0,
                start_date=today - datetime.timedelta(days=1),
                end_date=today + datetime.timedelta(days=5)
            )
            assert offer.is_active is True
            
            active_offers_res = get_active_offers()
            assert "Grand Opening Discount" in active_offers_res
            assert "20.0% OFF" in active_offers_res

            # 5. Semantic Search via RAG tool
            # (using mock embeddings, distance is 0, so relevance is 1.0)
            search_res = search_receptionist_knowledge("cancellation rules", k=3)
            assert "Grand Opening Discount" in search_res
            assert "Cancellation Policy V2" in search_res

            # 6. Deactivate / Expire offer test
            # Update end date to yesterday and run deactivation
            service.update_special_offer(
                db=db_session,
                offer_id=offer.id,
                end_date=today - datetime.timedelta(days=1)
            )
            service.deactivate_expired_offers(db_session)
            
            # Confirm offer is now inactive in DB and not listed
            assert db_session.query(SpecialOffer).filter(SpecialOffer.id == offer.id).first().is_active is False
            assert "Grand Opening Discount" not in get_active_offers()


# ---------------------------------------------------------------------------
# Admin API Routes Integration Tests
# ---------------------------------------------------------------------------

def test_admin_routes_and_access(db_session, mock_embedding_model):
    """Tests admin upload and offer API endpoints with mocked authorization."""
    
    test_settings = Settings(
        environment="testing",
        database_url="sqlite:///:memory:",
        debug=True,
    )
    app = create_app(settings=test_settings)
    
    # 1. Override dependencies to bypass auth and db Session
    from api.deps import get_current_user
    from db import get_db
    
    mock_admin = User(
        email="admin@salonai.com",
        role=UserRole.ADMIN,
        is_active=True
    )
    
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[get_db] = lambda: db_session
    
    client = TestClient(app)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("services.receptionist_rag_service._RECEPTIONIST_KNOWLEDGE_DIR", tmpdir), \
             patch("tools.receptionist_rag_tools._RECEPTIONIST_KNOWLEDGE_DIR", tmpdir), \
             patch("tools.receptionist_rag_tools.SessionLocal", return_value=db_session):
            
            # Test 1: Upload text document via API
            upload_payload = {
                "title": "Refund Rules",
                "document_type": "refund_policy"
            }
            upload_file = {
                "file": ("refund.txt", b"No refunds are allowed after service is completed.", "text/plain")
            }
            
            response = client.post("/api/v1/admin/knowledge/upload", data=upload_payload, files=upload_file)
            assert response.status_code == 201
            assert response.json()["success"] is True
            assert response.json()["document"]["title"] == "Refund Rules"
            
            # Verify direct query via tools
            assert "Refund Rules" in get_refund_policy()

            # Test 2: List documents
            list_resp = client.get("/api/v1/admin/knowledge/documents")
            assert list_resp.status_code == 200
            assert len(list_resp.json()["documents"]) == 1

            # Test 3: Create offer via API
            offer_payload = {
                "title": "Summer Blowout",
                "description": "50% off blowouts.",
                "discount_pct": 50.0,
                "start_date": "2026-06-01",
                "end_date": "2026-06-30"
            }
            
            offer_resp = client.post("/api/v1/admin/offers", json=offer_payload)
            assert offer_resp.status_code == 201
            assert offer_resp.json()["success"] is True
            assert offer_resp.json()["offer"]["title"] == "Summer Blowout"

            # Test 4: Delete offer
            offer_id = offer_resp.json()["offer"]["id"]
            del_resp = client.delete(f"/api/v1/admin/offers/{offer_id}")
            assert del_resp.status_code == 200
            
            # Verify deleted offers are not returned in list
            list_offers_resp = client.get("/api/v1/admin/offers")
            assert len(list_offers_resp.json()["offers"]) == 0
