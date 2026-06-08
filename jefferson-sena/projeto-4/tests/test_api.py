"""Testes da API FastAPI."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "uda-habitacional"


def test_openapi_docs():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "Pipeline UDA" in schema["info"]["title"]
