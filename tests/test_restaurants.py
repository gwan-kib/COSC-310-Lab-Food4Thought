import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_restaurants_returns_representative_data(isolated_restaurants_path):
    expected = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))

    response = TestClient(app).get("/restaurants")

    assert response.status_code == 200
    assert response.json() == expected
    assert len(response.json()) >= 2


def test_restaurants_uses_current_configured_data(isolated_restaurants_path):
    records = [
        {
            "id": "isolated",
            "name": "Test Cafe",
            "cuisine": "Cafe",
            "description": "Only in temporary storage",
        }
    ]
    isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")

    response = TestClient(app).get("/restaurants")

    assert response.status_code == 200
    assert response.json() == records


def test_restaurants_returns_empty_list_for_empty_data(isolated_restaurants_path):
    isolated_restaurants_path.write_text("[]", encoding="utf-8")

    response = TestClient(app).get("/restaurants")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("contents", [None, "{broken", '[{"id": "invalid"}]'])
def test_restaurants_reports_data_failure_without_exposing_details(
    isolated_restaurants_path, contents
):
    if contents is None:
        isolated_restaurants_path.unlink()
    else:
        isolated_restaurants_path.write_text(contents, encoding="utf-8")

    response = TestClient(app).get("/restaurants")

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}


def test_restaurants_openapi_uses_restaurant_response_model():
    schema = TestClient(app).get("/openapi.json").json()

    operation = schema["paths"]["/restaurants"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["type"] == "array"
    assert response_schema["items"]["$ref"] == "#/components/schemas/Restaurant"


def test_restaurants_rejects_post():
    assert TestClient(app).post("/restaurants").status_code == 405
