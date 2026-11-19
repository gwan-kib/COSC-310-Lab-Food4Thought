"""Exercise #94 through the menu API and a disposable restaurant store.
A scoped test permission stands in for the pending staff identity integration.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.routes.restaurants import get_restaurant_service
from app.main import app
from app.repositories.restaurant import RestaurantRepository
from app.services.restaurant import RestaurantService


MENU = "/restaurants/restaurant-001/menu"
ITEM = MENU + "/items/item-001"


@pytest.fixture
def manager(isolated_restaurants_path, monkeypatch):
    def service():
        return RestaurantService(
            RestaurantRepository(isolated_restaurants_path),
            can_manage_menu=lambda restaurant_id: restaurant_id == "restaurant-001",
        )

    monkeypatch.setitem(app.dependency_overrides, get_restaurant_service, service)
    return TestClient(app)


def test_legacy_read_and_normal_save(isolated_restaurants_path):
    client = TestClient(app)
    records = json.loads(isolated_restaurants_path.read_bytes())
    for record in records:
        for item in record["menu_items"]:
            item.pop("available", None)
    records[1]["menu_items"][0]["available"] = False
    isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")
    before = isolated_restaurants_path.read_bytes()
    assert client.get(MENU).json()["items"][0]["available"] is True
    assert isolated_restaurants_path.read_bytes() == before
    assert client.patch(ITEM, json={"price": "10"}).status_code == 200
    saved = json.loads(isolated_restaurants_path.read_bytes())
    for original, updated in zip(records, saved, strict=True):
        for old, new in zip(original["menu_items"], updated["menu_items"], strict=True):
            assert new["available"] is old.get("available", True)


def test_toggle_survives_reload_and_unrelated_edit(manager, isolated_restaurants_path):
    original = manager.get(MENU).json()["items"][0]
    response = manager.patch(ITEM, json={"available": False})
    assert response.status_code == 200
    assert response.json() == {**original, "available": False}
    assert manager.patch(ITEM, json={"price": "6"}).json()["available"] is False
    assert RestaurantRepository(isolated_restaurants_path).get_record("restaurant-001").menu_items[0].available is False
    assert manager.get(MENU).json()["items"][0]["available"] is False
    assert manager.patch(ITEM, json={"available": True}).json()["available"] is True


@pytest.mark.parametrize("value", [None, 0, 1, "false", [], {}])
def test_invalid_flags_preserve_storage(isolated_restaurants_path, value):
    client = TestClient(app)
    before = isolated_restaurants_path.read_bytes()
    assert client.patch(ITEM, json={"available": value}).status_code == 422
    assert client.post(MENU + "/items", json={
        "name": "Soup", "description": "Hot", "price": "2", "available": value
    }).status_code == 422
    assert isolated_restaurants_path.read_bytes() == before


def test_explicit_availability_requires_permission(isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    client = TestClient(app)
    assert client.patch(ITEM, json={"available": False}).status_code == 401
    assert client.post(MENU + "/items", json={
        "name": "Soup", "description": "Hot", "price": "2", "available": False
    }).status_code == 401
    assert isolated_restaurants_path.read_bytes() == before


def test_manager_scope_and_missing_item(manager, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    body = {"available": False}
    assert manager.patch("/restaurants/restaurant-002/menu/items/item-003", json=body).status_code == 403
    assert manager.patch(MENU + "/items/item-003", json=body).status_code == 404
    assert isolated_restaurants_path.read_bytes() == before


def test_create_unavailable_item(manager):
    result = manager.post(MENU + "/items", json={
        "name": "Soup", "description": "Hot", "price": "2", "available": False
    })
    assert result.status_code == 201
    assert result.json()["available"] is False
    assert result.json() in manager.get(MENU).json()["items"]


def test_failed_availability_save(manager, isolated_restaurants_path, monkeypatch):
    before = isolated_restaurants_path.read_bytes()

    def fail_replace(*args):
        raise OSError("failed replacement")

    monkeypatch.setattr("app.repositories.restaurant.os.replace", fail_replace)
    result = manager.patch(ITEM, json={"available": False})
    assert result.status_code == 500
    assert result.json() == {"detail": "Restaurant data is unavailable"}
    assert isolated_restaurants_path.read_bytes() == before


def test_invalid_stored_flag_is_corruption(isolated_restaurants_path):
    records = json.loads(isolated_restaurants_path.read_bytes())
    records[0]["menu_items"][0]["available"] = "false"
    isolated_restaurants_path.write_text(json.dumps(records), encoding="utf-8")
    before = isolated_restaurants_path.read_bytes()
    assert TestClient(app).get(MENU).status_code == 500
    assert isolated_restaurants_path.read_bytes() == before
