import os
import sys
import tempfile
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db.models import Base, User, UserRole
from main import create_app
from core.config import Settings
from tests.test_receptionist_rag import MockEmbeddings

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
    real_close = db.close
    db.close = lambda: None
    yield db
    db.close = real_close
    db.close()

def test_knowledge_rebuild_api_endpoint(db_session):
    test_settings = Settings(
        environment="testing",
        database_url="sqlite:///:memory:",
        debug=True,
    )
    app = create_app(settings=test_settings)
    
    from api.deps import get_current_user
    from infrastructure.db import get_db
    
    mock_admin = User(
        email="admin@salonai.com",
        role=UserRole.ADMIN,
        is_active=True
    )
    
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[get_db] = lambda: db_session
    
    client = TestClient(app)
    
    mock_model = MockEmbeddings()
    with patch("rag.embeddings.get_embedding_model", return_value=mock_model), \
         patch("services.receptionist_rag_service.get_embedding_model", return_value=mock_model), \
         patch("tools.receptionist_rag_tools.get_embedding_model", return_value=mock_model):
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("services.receptionist_rag_service._RECEPTIONIST_KNOWLEDGE_DIR", tmpdir), \
                 patch("tools.receptionist_rag_tools._RECEPTIONIST_KNOWLEDGE_DIR", tmpdir):
                
                # Test POST /api/v1/admin/knowledge/rebuild
                response = client.post("/api/v1/admin/knowledge/rebuild")
                assert response.status_code == 200
                assert response.json()["success"] is True
                assert response.json()["details"]["index_name"] == "receptionist_knowledge"
                assert isinstance(response.json()["details"]["chunks_indexed"], int)

