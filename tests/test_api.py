from fastapi.testclient import TestClient

from app.main import app


def test_health_and_openapi():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    schema = client.get("/openapi.json").json()
    assert "/v1/generate" in schema["paths"]

