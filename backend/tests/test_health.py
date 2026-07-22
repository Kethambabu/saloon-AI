"""Health check endpoint tests"""

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert "version" in data


def test_api_root(client):
    """Test API v1 root endpoint"""
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data

