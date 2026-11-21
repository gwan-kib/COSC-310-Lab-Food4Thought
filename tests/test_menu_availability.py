"""Exercise #94 through the menu API and a disposable restaurant store.
Sign in through the real login route and exercise cart and checkout against the same files.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_auth_service, get_now
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.services.catalog import RestaurantCatalog
from app.repositories.customer import CustomerRepository
from app.schemas.order import CheckoutRequest
from app.services.checkout import CheckoutConflict, CheckoutService
from app.services.customer import CustomerService
from app.core.workflow import workflow_lock
from app.main import app
from app.repositories.restaurant import RestaurantRepository


MENU = "/restaurants/restaurant-001/menu"
ITEM = MENU + "/items/item-001"


def sign_in(accounts, role):
    account = accounts.accounts[role]
    client = TestClient(app)
    response = client.post("/auth/login", json={
        "email": account.record.email, "password": account.password,
    })
    assert response.status_code == 200
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return client


@pytest.fixture
def manager(auth_accounts):
    return sign_in(auth_accounts, "restaurant_user")


def test_legacy_read_and_normal_save(isolated_restaurants_path, manager):
    client = manager
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
def test_invalid_flags_preserve_storage(isolated_restaurants_path, value, manager):
    client = manager
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

@pytest.mark.parametrize("role", ["customer_a", "administrator"])
def test_wrong_role_precedes_validation(auth_accounts, isolated_restaurants_path, role):
    client = sign_in(auth_accounts, role)
    before = isolated_restaurants_path.read_bytes()
    for body in ({"available": "false"}, {"price": "5"}):
        assert client.patch(ITEM, json=body).status_code == 403
    assert isolated_restaurants_path.read_bytes() == before


def test_missing_token_precedes_validation():
    result = TestClient(app).patch(ITEM, json={"available": "false"})
    assert (result.status_code, result.headers["www-authenticate"]) == (401, "Bearer")


def test_manager_cannot_edit_missing_restaurant(manager):
    assert manager.patch("/restaurants/missing/menu/items/item-001",
                         json={"available": False}).status_code == 404


def test_current_availability_from_cart_add_through_checkout(manager, auth_accounts):
    customer = sign_in(auth_accounts, "customer_a")
    cart_path = "/customers/me/cart"
    add = {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 1}
    assert customer.put(cart_path).status_code == 201
    assert manager.patch(ITEM, json={"available": False}).status_code == 200
    cart_store = auth_accounts.paths["carts"]
    before = cart_store.read_bytes()
    denied = customer.post(cart_path + "/items", json=add)
    assert (denied.status_code, denied.json()) == (409, {"detail": "Menu item is unavailable"})
    assert cart_store.read_bytes() == before

    assert manager.patch(ITEM, json={"available": True}).status_code == 200
    added = customer.post(cart_path + "/items", json=add)
    assert added.status_code == 200
    cart = added.json()
    before = cart_store.read_bytes()
    orders_before = auth_accounts.paths["orders"].read_bytes()
    assert manager.patch(ITEM, json={"available": False}).status_code == 200
    assert customer.get(cart_path).json()["items"][0]["available"] is False

    principal, checkout = checkout_for(customer)
    request = CheckoutRequest(cart_id=cart["id"], cart_revision=cart["revision"])
    with pytest.raises(CheckoutConflict, match="Menu item is unavailable"):
        checkout.checkout(principal, request)
    assert cart_store.read_bytes() == before
    assert auth_accounts.paths["orders"].read_bytes() == orders_before


def checkout_for(customer):
    token = customer.headers["Authorization"].removeprefix("Bearer ")
    principal = get_auth_service().resolve(token, get_now())
    checkout = CheckoutService(CustomerService(CustomerRepository()).active_customer_for,
                               CartRepository(), RestaurantCatalog(), OrderRepository())
    return principal, checkout

def test_checkout_waits_for_an_inflight_disable(manager, auth_accounts, monkeypatch):
    customer = sign_in(auth_accounts, "customer_a")
    assert customer.put("/customers/me/cart").status_code == 201
    added = customer.post("/customers/me/cart/items", json={
        "restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 1,
    })
    assert added.status_code == 200
    cart = added.json()
    request = CheckoutRequest(cart_id=cart["id"], cart_revision=cart["revision"])
    principal, checkout = checkout_for(customer)
    before = {name: auth_accounts.paths[name].read_bytes() for name in ("carts", "orders")}
    saving, attempted = Event(), Event()
    save = RestaurantRepository._save_records

    def pause_before_save(repository, records):
        saving.set()
        assert attempted.wait(5)
        save(repository, records)

    class ObservedCheckoutLock:
        def __enter__(self):
            # The manager is paused just before replacement, still holding the workflow lock.
            try:
                assert workflow_lock.locked()
            finally:
                attempted.set()
            workflow_lock.acquire()

        def __exit__(self, *_):
            workflow_lock.release()

    monkeypatch.setattr(RestaurantRepository, "_save_records", pause_before_save)
    monkeypatch.setattr("app.services.checkout.workflow_lock", ObservedCheckoutLock())
    with ThreadPoolExecutor(max_workers=1) as pool:
        toggle = pool.submit(manager.patch, ITEM, json={"available": False})
        assert saving.wait(5)
        with pytest.raises(CheckoutConflict, match="Menu item is unavailable"):
            checkout.checkout(principal, request)
        assert toggle.result(timeout=5).status_code == 200
    assert {name: auth_accounts.paths[name].read_bytes() for name in before} == before
