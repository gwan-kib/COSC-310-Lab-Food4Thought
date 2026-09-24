from fastapi.testclient import TestClient


def test_health_returns_ok():
    from app.main import app

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_docs_are_served():
    from app.main import app

    response = TestClient(app).get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_health_lists_only_get_in_openapi_schema():
    from app.main import app

    schema = TestClient(app).get("/openapi.json").json()

    assert set(schema["paths"]["/health"]) == {"get"}


def test_health_rejects_unsupported_method():
    from app.main import app

    response = TestClient(app).post("/health")

    assert response.status_code == 405
