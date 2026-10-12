import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.restaurant import RestaurantDataError, RestaurantRepository


@pytest.fixture(params=["create", "update"])
def write_item(request):
    client = TestClient(app)

    def write(price):
        if request.param == "create":
            response = client.post(
                "/restaurants/restaurant-001/menu/items",
                json={"name": "Soup", "description": "Hot soup", "price": price},
            )
        else:
            response = client.patch(
                "/restaurants/restaurant-001/menu/items/item-001",
                json={"price": price},
            )
        return response

    return write, 201 if request.param == "create" else 200


@pytest.mark.parametrize(
    "price, expected",
    [("0", "0.00"), ("998.99", "998.99"), ("999", "999.00"),
     ("999.0", "999.00"), ("999.00", "999.00"), ("000999.00", "999.00")],
)
def test_price_limit_accepts_inclusive_maximum_and_normalizes(
    isolated_restaurants_path, write_item, price, expected
):
    write, expected_status = write_item

    response = write(price)

    assert response.status_code == expected_status
    assert response.json()["price"] == expected
    saved = RestaurantRepository(isolated_restaurants_path).get_record("restaurant-001")
    item = next(item for item in saved.menu_items if item.id == response.json()["id"])
    assert item.price == expected


@pytest.mark.parametrize(
    "price", ["999.01", "999.99", "1000", "000999.01", pytest.param("9" * 1000, id="large-value")]
)
def test_price_limit_rejects_above_maximum_without_writing(
    isolated_restaurants_path, write_item, price
):
    before = isolated_restaurants_path.read_bytes()
    write, _ = write_item

    response = write(price)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert isolated_restaurants_path.read_bytes() == before


@pytest.mark.parametrize("model_name", ["MenuItemCreate", "MenuItemUpdate", "MenuItem"])
def test_price_limit_is_documented_on_request_and_read_models(model_name):
    schema = TestClient(app).get("/openapi.json").json()
    price = schema["components"]["schemas"][model_name]["properties"]["price"]

    assert price["type"] == "string"
    assert "999.00" in price["description"]


@pytest.mark.parametrize("price", ["999.01", "1000.00", "000999.01"])
def test_repository_rejects_stored_prices_above_limit_without_rewriting(
    isolated_restaurants_path, price
):
    records = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    records[1]["menu_items"][0]["price"] = price
    isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")
    before = isolated_restaurants_path.read_bytes()

    with pytest.raises(RestaurantDataError):
        RestaurantRepository(isolated_restaurants_path).load_records()

    assert isolated_restaurants_path.read_bytes() == before


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("GET", "/restaurants", None),
        ("GET", "/restaurants/restaurant-001/menu", None),
        ("POST", "/restaurants", {"name": "New", "cuisine": "Cafe", "description": "Food"}),
        ("PATCH", "/restaurants/restaurant-001", {"name": "New"}),
        ("POST", "/restaurants/restaurant-001/menu/items",
         {"name": "Soup", "description": "Hot", "price": "5.00"}),
        ("PATCH", "/restaurants/restaurant-001/menu/items/item-001", {"price": "5.00"}),
    ],
)
def test_out_of_range_stored_price_returns_generic_500_across_operations(
    isolated_restaurants_path, method, path, body
):
    records = json.loads(isolated_restaurants_path.read_text(encoding="utf-8"))
    # Invalid data in another restaurant must not be ignored or silently repaired.
    records[1]["menu_items"][0]["price"] = "999.01"
    isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).request(method, path, json=body)

    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable"}
    assert isolated_restaurants_path.read_bytes() == before


def test_repository_revalidates_price_limit_before_save(isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()

    def invalid_change(records):
        records[0].menu_items[0].price = "999.01"

    with pytest.raises(RestaurantDataError):
        RestaurantRepository(isolated_restaurants_path).mutate_records(invalid_change)

    assert isolated_restaurants_path.read_bytes() == before


def test_price_limit_validation_precedes_storage_access(isolated_restaurants_path, write_item):
    isolated_restaurants_path.unlink()
    write, _ = write_item

    assert write("999.01").status_code == 422
    assert not isolated_restaurants_path.exists()
