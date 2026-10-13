# Verify Food4Thought's cuisine filtering through HTTP and direct service calls
# using isolated records. Protect whole-value casefold matching, stored order and
# spelling, and validation of blank queries before storage access without changing
# unfiltered results.

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.restaurant import RestaurantRepository
from app.services.restaurant import RestaurantService


def _restaurant(identifier, cuisine):
    return {
        "id": identifier,
        "name": f"Restaurant {identifier}",
        "cuisine": cuisine,
        "description": "Test kitchen",
    }


RESTAURANTS = [
    _restaurant("a", "Japanese"),
    _restaurant("b", "Italian"),
    _restaurant("c", "japanese"),
    _restaurant("d", "Japanese Fusion"),
    _restaurant("e", "Straße Food"),
]


@pytest.fixture
def filter_data(isolated_restaurants_path):
    isolated_restaurants_path.write_text(json.dumps(RESTAURANTS), encoding="utf-8")
    return isolated_restaurants_path


def _ids(response):
    return [restaurant["id"] for restaurant in response.json()]


# Matching


def test_unfiltered_list_is_unchanged(filter_data):
    response = TestClient(app).get("/restaurants")

    assert response.status_code == 200
    assert response.json() == RESTAURANTS


@pytest.mark.parametrize("query", ["Japanese", "japanese", "JAPANESE", "  JAPANESE  "])
def test_filter_matches_whole_cuisine_ignoring_case_and_whitespace(filter_data, query):
    response = TestClient(app).get("/restaurants", params={"cuisine": query})

    assert response.status_code == 200
    assert _ids(response) == ["a", "c"]


def test_filter_preserves_stored_spelling_and_order(filter_data):
    response = TestClient(app).get("/restaurants", params={"cuisine": "japanese"})

    assert [restaurant["cuisine"] for restaurant in response.json()] == [
        "Japanese",
        "japanese",
    ]


def test_filter_requires_whole_value_not_prefix(filter_data):
    response = TestClient(app).get("/restaurants", params={"cuisine": "Japan"})

    assert response.status_code == 200
    assert response.json() == []


def test_filter_uses_casefold_rather_than_lower(filter_data):
    # "ß".lower() stays "ß", but casefold() turns it into "ss".
    response = TestClient(app).get("/restaurants", params={"cuisine": "STRASSE FOOD"})

    assert _ids(response) == ["e"]


def test_filter_returns_empty_list_when_nothing_matches(filter_data):
    response = TestClient(app).get("/restaurants", params={"cuisine": "Peruvian"})

    assert response.status_code == 200
    assert response.json() == []


def test_unrecognized_query_parameters_are_ignored(filter_data):
    response = TestClient(app).get("/restaurants", params={"name": "Restaurant a"})

    assert response.json() == RESTAURANTS


def test_filter_does_not_write_storage(filter_data):
    before = filter_data.read_bytes()

    TestClient(app).get("/restaurants", params={"cuisine": "Italian"})

    assert filter_data.read_bytes() == before


# Validation and failures


@pytest.mark.parametrize("query", ["", "   ", "\t"])
def test_blank_filter_returns_422(filter_data, query):
    response = TestClient(app).get("/restaurants", params={"cuisine": query})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["loc"] == ["query", "cuisine"]


def test_blank_filter_is_rejected_before_storage_is_read(isolated_restaurants_path):
    isolated_restaurants_path.write_text("{broken", encoding="utf-8")

    response = TestClient(app).get("/restaurants", params={"cuisine": " "})

    assert response.status_code == 422


def test_filter_reports_storage_failure(isolated_restaurants_path):
    isolated_restaurants_path.unlink()

    response = TestClient(app).get("/restaurants", params={"cuisine": "Japanese"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}


# Documentation and service


def test_filter_openapi_documents_query_parameter():
    schema = TestClient(app).get("/openapi.json").json()
    operation = schema["paths"]["/restaurants"]["get"]

    parameter = next(p for p in operation["parameters"] if p["name"] == "cuisine")
    assert parameter["in"] == "query"
    assert parameter["required"] is False
    assert parameter["description"]
    assert set(operation["responses"]) == {"200", "422", "500"}
    assert "cuisine" in operation["description"]


def test_service_filters_by_cuisine(filter_data):
    service = RestaurantService(RestaurantRepository(filter_data))

    assert [r.id for r in service.list_restaurants()] == ["a", "b", "c", "d", "e"]
    assert [r.id for r in service.list_restaurants(cuisine=" ITALIAN ")] == ["b"]
