import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.restaurant import RestaurantDataError, RestaurantRepository
from app.schemas.restaurant import Menu, RestaurantRecord
from app.services.restaurant import RestaurantService

COMMITTED_DATA = Path(__file__).resolve().parents[1] / "data" / "restaurants.json"


def _item(identifier, name="Dish", price="10.00"):
    return {"id": identifier, "name": name, "description": "Tasty", "price": price}


def _restaurant(identifier, menu_items=None):
    record = {
        "id": identifier,
        "name": f"Restaurant {identifier}",
        "cuisine": "Fusion",
        "description": "Test kitchen",
    }
    if menu_items is not None:
        record["menu_items"] = menu_items
    return record


def _write(path, records):
    path.write_text(json.dumps(records), encoding="utf-8")


# Representative data


def test_committed_data_includes_valid_menus_for_each_restaurant():
    records = json.loads(COMMITTED_DATA.read_text(encoding="utf-8"))

    validated = [RestaurantRecord.model_validate(record) for record in records]

    assert len(validated) >= 2
    assert all(record.menu_items for record in validated)


def test_menu_returns_representative_items(isolated_restaurants_path):
    record = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))[0]

    response = TestClient(app).get(f"/restaurants/{record['id']}/menu")

    assert response.status_code == 200
    assert response.json() == {
        "restaurant_id": record["id"],
        "items": record["menu_items"],
    }


# Endpoint behaviour


def test_menu_only_contains_items_of_requested_restaurant(isolated_restaurants_path):
    _write(
        isolated_restaurants_path,
        [
            _restaurant("restaurant-a", [_item("shared-id", "A dish")]),
            _restaurant("restaurant-b", [_item("shared-id", "B dish"), _item("b-2")]),
        ],
    )

    response = TestClient(app).get("/restaurants/restaurant-b/menu")

    assert response.status_code == 200
    assert response.json()["restaurant_id"] == "restaurant-b"
    assert [item["name"] for item in response.json()["items"]] == ["B dish", "Dish"]


def test_menu_is_empty_for_legacy_record_without_menu_items(isolated_restaurants_path):
    _write(isolated_restaurants_path, [_restaurant("legacy")])
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).get("/restaurants/legacy/menu")

    assert response.status_code == 200
    assert response.json() == {"restaurant_id": "legacy", "items": []}
    assert isolated_restaurants_path.read_bytes() == before


def test_menu_serializes_prices_with_two_decimals(isolated_restaurants_path):
    _write(isolated_restaurants_path, [_restaurant("r", [_item("i", price="9.5")])])

    response = TestClient(app).get("/restaurants/r/menu")

    assert response.json()["items"][0]["price"] == "9.50"


def test_menu_returns_404_for_unknown_restaurant():
    response = TestClient(app).get("/restaurants/does-not-exist/menu")

    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}


@pytest.mark.parametrize(
    "records",
    [
        pytest.param(None, id="missing-file"),
        pytest.param("{broken", id="malformed-json"),
        pytest.param([_restaurant("r", None) | {"menu_items": None}], id="null-menu"),
        pytest.param([_restaurant("r", [{"id": "i", "name": "No price"}])], id="invalid-item"),
        pytest.param([_restaurant("r", [_item("i", price="-1")])], id="invalid-price"),
        pytest.param([_restaurant("r", [_item("dup"), _item("dup")])], id="duplicate-item-ids"),
        pytest.param([_restaurant("r", []), _restaurant("r", [])], id="duplicate-restaurant-ids"),
    ],
)
def test_menu_reports_corrupt_data_without_exposing_details(
    isolated_restaurants_path, records
):
    if records is None:
        isolated_restaurants_path.unlink()
    elif isinstance(records, str):
        isolated_restaurants_path.write_text(records, encoding="utf-8")
    else:
        _write(isolated_restaurants_path, records)

    response = TestClient(app).get("/restaurants/r/menu")

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}


def test_restaurant_list_shape_excludes_menu_items(isolated_restaurants_path):
    _write(isolated_restaurants_path, [_restaurant("r", [_item("i")])])

    response = TestClient(app).get("/restaurants")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "r",
            "name": "Restaurant r",
            "cuisine": "Fusion",
            "description": "Test kitchen",
        }
    ]


def test_menu_openapi_documents_contract():
    schema = TestClient(app).get("/openapi.json").json()
    operation = schema["paths"]["/restaurants/{restaurant_id}/menu"]["get"]

    assert operation["description"]
    parameter = operation["parameters"][0]
    assert parameter["name"] == "restaurant_id"
    assert parameter["in"] == "path"
    assert parameter["description"]

    responses = operation["responses"]
    assert set(responses) == {"200", "404", "500"}
    ok_schema = responses["200"]["content"]["application/json"]["schema"]
    assert ok_schema["$ref"] == "#/components/schemas/Menu"
    for status in ("404", "500"):
        error_schema = responses[status]["content"]["application/json"]["schema"]
        assert error_schema["$ref"] == "#/components/schemas/ErrorResponse"

    menu_schema = schema["components"]["schemas"]["Menu"]
    assert set(menu_schema["required"]) == {"restaurant_id", "items"}
    assert menu_schema["properties"]["items"]["items"]["$ref"] == (
        "#/components/schemas/MenuItem"
    )


# Service and repository


def test_service_builds_menu_from_record(isolated_restaurants_path):
    _write(isolated_restaurants_path, [_restaurant("r", [_item("i", "Soup")])])
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    menu = service.get_menu("r")

    assert isinstance(menu, Menu)
    assert menu.restaurant_id == "r"
    assert [item.name for item in menu.items] == ["Soup"]


def test_service_raises_not_found_for_unknown_menu(isolated_restaurants_path):
    from app.services.restaurant import RestaurantNotFoundError

    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    with pytest.raises(RestaurantNotFoundError):
        service.get_menu("does-not-exist")


def test_service_menu_preserves_repository_failure(isolated_restaurants_path):
    isolated_restaurants_path.unlink()
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path))

    with pytest.raises(RestaurantDataError):
        service.get_menu("r")


def test_repository_gets_complete_record_by_id(isolated_restaurants_path):
    _write(
        isolated_restaurants_path,
        [_restaurant("a", [_item("a-1")]), _restaurant("b", [_item("b-1")])],
    )
    repository = RestaurantRepository(isolated_restaurants_path)

    record = repository.get_record("b")

    assert record is not None
    assert [item.id for item in record.menu_items] == ["b-1"]
    assert repository.get_record("missing") is None
