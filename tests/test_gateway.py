"""Basic gateway integration tests."""

import pytest
from fastapi.testclient import TestClient

from gateway.api.app import app


@pytest.fixture
def client():
    """Test client for the gateway app."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    """Health check tests."""

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestModelsEndpoint:
    """Model listing tests."""

    def test_list_models_returns_list(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)


class TestChatEndpoint:
    """Chat completion endpoint tests."""

    def test_missing_auth_returns_401(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "llama3.2:1b",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 401

    def test_valid_auth_but_no_backend(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "llama3.2:1b",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers={"Authorization": "Bearer dev-key-1"},
        )
        # 503 because no backends are running in test
        assert response.status_code in (503, 502)
