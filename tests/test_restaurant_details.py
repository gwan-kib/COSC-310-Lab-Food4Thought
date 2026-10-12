import json

import pytest
from fastapi.testclient import TestClient

from app.api.openapi import CONTRACT_NO_VALIDATION_ERROR_OPERATIONS
from app.main import app
from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import Restaurant
from app.services.restaurant import RestaurantNotFoundError, RestaurantService

READ_FIELDS = ("id", "name", "cuisine", "description")


def _restaurant(identifier, **overrides):
    record = {
        "id": identifier,
        "name": f"Restaurant {identifier}",
        "cuisine": "Fusion",
        "description": "Test kitchen",
    }
    record.update(overrides)
    return record


def _write(path, records):
    path.write_text(json.dumps(records), encoding="utf-8")


# Endpoint behaviour


def test_details_returns_representative_restaurant_without_menu(isolated_restaurants_path):
    record = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))[0]

    response = TestClient(app).get(f"/restaurants/{record['id']}")

    assert response.status_code == 200
    assert response.json() == {field: record[field] for field in READ_FIELDS}


def test_details_reads_currently_configured_data(isolated_restaurants_path):
    _write(
        isolated_restaurants_path,
        [_restaurant("a"), _restaurant("isolated-only", name="Test Cafe")],
    )

    response = TestClient(app).get("/restaurants/isolated-only")

    assert response.status_code == 200
    assert response.json()["name"] == "Test Cafe"


def test_details_compares_ids_exactly(isolated_restaurants_path):
    _write(isolated_restaurants_path, [_restaurant("restaurant-a")])

    assert TestClient(app).get("/restaurants/RESTAURANT-A").status_code == 404


def test_details_returns_404_for_unknown_restaurant():
    response = TestClient(app).get("/restaurants/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}


def test_details_does_not_write_storage(isolated_restaurants_path):
    _write(isolated_restaurants_path, [_restaurant("legacy")])
    before = isolated_restaurants_path.read_bytes()

    TestClient(app).get("/restaurants/legacy")
    TestClient(app).get("/restaurants/unknown")

    assert isolated_restaurants_path.read_bytes() == before


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param(None, id="missing-file"),
        pytest.param("{broken", id="malformed-json"),
        pytest.param('[{"id": "r"}]', id="invalid-record"),
        pytest.param(json.dumps([_restaurant("r"), _restaurant("r")]), id="duplicate-ids"),
    ],
)
def test_details_reports_storage_failure_without_details(
    isolated_restaurants_path, contents
):
    if contents is None:
        isolated_restaurants_path.unlink()
    else:
        isolated_restaurants_path.write_text(contents, encoding="utf-8")

    # An unknown ID against corrupt storage is still a storage failure, not a 404.
    for restaurant_id in ("r", "unknown"):
        response = TestClient(app).get(f"/restaurants/{restaurant_id}")

        assert response.status_code == 500
        assert response.json() == {"detail": "Restaurant data is unavailable"}


def test_details_openapi_documents_contract():
    schema = TestClient(app).get("/openapi.json").json()
    operation = schema["paths"]["/restaurants/{restaurant_id}"]["get"]

    assert operation["summary"]
    assert operation["description"]
    parameter = operation["parameters"][0]
    assert parameter["name"] == "restaurant_id"
    assert parameter["in"] == "path"
    assert parameter["required"] is True
    assert parameter["description"]

    responses = operation["responses"]
    assert set(responses) == {"200", "404", "500"}
    ok_schema = responses["200"]["content"]["application/json"]["schema"]
    assert ok_schema["$ref"] == "#/components/schemas/Restaurant"
    for status in ("404", "500"):
        error_schema = responses[status]["content"]["application/json"]["schema"]
        assert error_schema["$ref"] == "#/components/schemas/ErrorResponse"


def test_contract_list_names_the_details_operation():
    assert ("get", "/restaurants/{restaurant_id}") in CONTRACT_NO_VALIDATION_ERROR_OPERATIONS


# Service


def test_service_projects_stored_record_to_restaurant(isolated_restaurants_path):
    menu_item = {"id": "i", "name": "Soup", "description": "Hot", "price": "4.50"}
    _write(isolated_restaurants_path, [_restaurant("r", menu_items=[menu_item])])
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    restaurant = service.get_restaurant("r")

    assert restaurant == Restaurant(**_restaurant("r"))


def test_service_raises_not_found_for_unknown_restaurant(isolated_restaurants_path):
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    with pytest.raises(RestaurantNotFoundError):
        service.get_restaurant("does-not-exist")


def test_service_details_preserves_repository_failure(isolated_restaurants_path):
    isolated_restaurants_path.unlink()
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    with pytest.raises(RestaurantDataError):
        service.get_restaurant("r")
