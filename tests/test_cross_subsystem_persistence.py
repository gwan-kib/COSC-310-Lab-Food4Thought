"""Verify Food4Thought identifiers and relationships across real M2 HTTP workflows.
Exercise six isolated JSON stores, fresh application/repository instances and failure
boundaries without replacing the customer, cart, restaurant or order implementations.
"""

import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.api.routes import carts, checkout, customers, order_details, order_history
from app.main import app
from app.repositories.cart import CartRepository
from app.repositories.customer import CustomerRepository, SessionRepository
from app.repositories.order import OrderRepository
from app.repositories.restaurant import RestaurantRepository
from app.repositories.staff import StaffRepository

CART = "/customers/me/cart"
CHECKOUT = "/customers/me/checkout"
FIRST = {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2}
SECOND = {"restaurant_id": "restaurant-002", "item_id": "item-003", "quantity": 1}
STORES = ("restaurants", "customers", "carts", "orders", "staff", "sessions")


@pytest.fixture
def client(auth_accounts, monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


def _bytes(paths):
    return {name: paths[name].read_bytes() for name in STORES}


def _cart_with_item(client, headers, item=FIRST):
    initial = client.put(CART, headers=headers)
    assert initial.status_code in (200, 201)
    added = client.post(f"{CART}/items", headers=headers, json=item)
    assert added.status_code == 200, added.text
    return added.json()


def _fresh_app(now):
    """Recompose routes so all dependencies construct repositories from the same disk paths."""
    fresh = FastAPI()
    for router in (customers.router, carts.router, checkout.router,
                   order_history.router, order_details.router):
        fresh.include_router(router)
    fresh.dependency_overrides[get_now] = lambda: now
    return fresh


def test_two_customers_two_orders_reopen_with_stable_relationships(
        client, auth_accounts, m2_store_paths):
    ada = auth_accounts.headers("customer_a")
    ben = auth_accounts.headers("customer_b")
    original = client.put(CART, headers=ada)
    assert original.status_code == 201
    ada_id = original.json()["id"]
    assert client.put(CART, headers=ada).json()["id"] == ada_id
    ben_cart = client.put(CART, headers=ben)
    assert ben_cart.status_code == 201
    assert ben_cart.json()["id"] != ada_id

    first = _cart_with_item(client, ada)
    assert (first["id"], first["customer_id"], first["restaurant_id"]) == (
        ada_id, "customer-001", "restaurant-001")
    assert first["items"][0]["item_id"] == "item-001"
    attempt1 = {"cart_id": ada_id, "cart_revision": first["revision"]}
    bought1 = client.post(CHECKOUT, headers=ada, json=attempt1)
    assert bought1.status_code == 201
    order1 = bought1.json()["order"]
    assert (order1["customer_id"], order1["restaurant_id"],
            order1["source_cart_id"], order1["source_cart_revision"]) == (
                "customer-001", "restaurant-001", ada_id, first["revision"])
    assert order1["items"] == [{
        "item_id": "item-001", "name": "Vegetable bowl", "quantity": 2,
        "unit_price": "12.50", "line_total": "25.00",
    }]
    assert order1["subtotal"] == order1["total"] == "25.00"
    assert client.post(CHECKOUT, headers=ada, json=attempt1).json()["order"] == order1

    assert client.patch("/customers/me", headers=ada,
                        json={"delivery_address": "New test-only address"}).status_code == 200
    assert client.patch("/restaurants/restaurant-001/menu/items/item-001",
                        headers=auth_accounts.headers("restaurant_user"),
                        json={"name": "Updated bowl", "price": "19.00"}).status_code == 200

    second = _cart_with_item(client, ada, SECOND)
    assert second["id"] == ada_id and second["restaurant_id"] == "restaurant-002"
    attempt2 = {"cart_id": ada_id, "cart_revision": second["revision"]}
    bought2 = client.post(CHECKOUT, headers=ada, json=attempt2)
    assert bought2.status_code == 201
    order2 = bought2.json()["order"]
    assert order2["id"] != order1["id"]
    assert (order2["restaurant_id"], order2["source_cart_id"],
            order2["source_cart_revision"], order2["items"][0]["item_id"]) == (
                "restaurant-002", ada_id, second["revision"], "item-003")
    assert order2["total"] == "15.00"

    carts_on_disk = CartRepository(m2_store_paths["carts"]).load_carts()
    assert len(carts_on_disk) == 2
    assert {cart.customer_id: cart.id for cart in carts_on_disk} == {
        "customer-001": ada_id, "customer-002": ben_cart.json()["id"],
    }
    orders_on_disk = OrderRepository(m2_store_paths["orders"]).list_for_customer("customer-001")
    assert [order.model_dump(mode="json") for order in orders_on_disk] == [order1, order2]
    before_read = _bytes(m2_store_paths)

    with TestClient(_fresh_app(auth_accounts.now), raise_server_exceptions=False) as reopened:
        assert reopened.put(CART, headers=ada).json()["id"] == ada_id
        assert reopened.get(CART, headers=ben).json() == ben_cart.json()
        assert reopened.get("/customers/me/orders", headers=ada).json() == [order1, order2]
        assert reopened.get("/customers/me/orders", headers=ben).json() == []
        assert reopened.get(f"/customers/me/orders/{order1['id']}", headers=ada).json() == order1
        assert reopened.post(CHECKOUT, headers=ada, json=attempt1).json() == {
            "order": order1, "cart_reset_pending": False,
        }
        assert reopened.get(CART, headers=ada).json()["id"] == ada_id
    assert _bytes(m2_store_paths) == before_read


@pytest.mark.parametrize("corruption", ["missing_restaurant", "missing_item", "wrong_parent_item",
                                        "duplicate_customer_cart"])
def test_invalid_cart_relationships_never_trigger_checkout_writes(
        client, auth_accounts, m2_store_paths, monkeypatch, corruption):
    ada = auth_accounts.headers("customer_a")
    cart = _cart_with_item(client, ada)
    records = json.loads(m2_store_paths["carts"].read_text(encoding="utf-8"))
    if corruption == "missing_restaurant":
        records[0]["restaurant_id"] = "unknown-restaurant"
    elif corruption == "missing_item":
        records[0]["items"][0]["item_id"] = "unknown-item"
    elif corruption == "wrong_parent_item":
        # item-003 exists, but only inside restaurant-002.
        records[0]["items"][0]["item_id"] = "item-003"
    else:
        records.append({**records[0], "id": "second-cart"})
    m2_store_paths["carts"].write_text(json.dumps(records) + "\n", encoding="utf-8")
    before = _bytes(m2_store_paths)
    writes = []
    original_replace = os.replace

    def trace_replace(source, destination):
        writes.append(Path(destination))
        return original_replace(source, destination)

    with monkeypatch.context() as trace:
        trace.setattr(os, "replace", trace_replace)
        view = client.get(CART, headers=ada)
        response = client.post(CHECKOUT, headers=ada, json={
            "cart_id": cart["id"], "cart_revision": cart["revision"],
        })

    assert (view.status_code, view.json()) == (500, {"detail": "Cart data is unavailable"})
    assert (response.status_code, response.json()) == (500, {"detail": "Checkout data is unavailable"})
    assert writes == []
    assert _bytes(m2_store_paths) == before


@pytest.mark.parametrize("store,method,path,detail", [
    ("customers", "get", CART, "Authentication data is unavailable"),
    ("sessions", "get", CART, "Authentication data is unavailable"),
    ("carts", "get", CART, "Cart data is unavailable"),
    ("orders", "get", CART, "Cart data is unavailable"),
    ("restaurants", "get", "/restaurants", "Restaurant data is unavailable"),
    ("staff", "post", "/auth/login", "Authentication data is unavailable"),
])
def test_corrupt_store_returns_its_public_error_without_other_writes(
        client, auth_accounts, m2_store_paths, store, method, path, detail):
    ada = auth_accounts.headers("customer_a")
    _cart_with_item(client, ada)
    m2_store_paths[store].write_bytes(b"{not valid JSON")
    before = _bytes(m2_store_paths)

    if store == "staff":
        account = auth_accounts.accounts["restaurant_user"]
        response = client.post(path, json={
            "email": account.record.email, "password": account.password,
        })
    else:
        response = client.request(method, path, headers=ada)
    assert (response.status_code, response.json()) == (500, {"detail": detail})
    assert _bytes(m2_store_paths) == before


@pytest.mark.parametrize("store", ["carts", "orders", "restaurants"])
def test_unreadable_store_is_not_silently_recreated(
        client, auth_accounts, m2_store_paths, monkeypatch, store):
    ada = auth_accounts.headers("customer_a")
    _cart_with_item(client, ada)
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    target = m2_store_paths[store]
    before = _bytes(m2_store_paths)

    def deny_bytes(path):
        if path == target:
            raise PermissionError("simulated unreadable storage")
        return original_read_bytes(path)

    def deny_text(path, *args, **kwargs):
        if path == target:
            raise PermissionError("simulated unreadable storage")
        return original_read_text(path, *args, **kwargs)

    with monkeypatch.context() as denied:
        # RestaurantRepository reads text; cart/order repositories read bytes.
        denied.setattr(Path, "read_bytes", deny_bytes)
        denied.setattr(Path, "read_text", deny_text)
        if store == "restaurants":
            response = client.get("/restaurants")
            detail = "Restaurant data is unavailable"
        else:
            response = client.get(CART, headers=ada)
            detail = "Cart data is unavailable"

    assert (response.status_code, response.json()) == (500, {"detail": detail})
    assert _bytes(m2_store_paths) == before


@pytest.mark.parametrize("failed_store", ["orders", "carts"])
def test_checkout_replace_failure_has_only_the_agreed_partial_state(
        client, auth_accounts, m2_store_paths, monkeypatch, failed_store):
    ada = auth_accounts.headers("customer_a")
    cart = _cart_with_item(client, ada)
    attempt = {"cart_id": cart["id"], "cart_revision": cart["revision"]}
    before = _bytes(m2_store_paths)
    original_replace = os.replace
    attempted = []

    def fail_one(source, destination):
        attempted.append(Path(destination))
        if Path(destination) == m2_store_paths[failed_store]:
            raise OSError("simulated replacement failure")
        return original_replace(source, destination)

    with monkeypatch.context() as failing:
        failing.setattr(os, "replace", fail_one)
        response = client.post(CHECKOUT, headers=ada, json=attempt)

    if failed_store == "orders":
        assert (response.status_code, response.json()) == (
            500, {"detail": "Checkout data is unavailable"})
        assert attempted == [m2_store_paths["orders"]]
        assert _bytes(m2_store_paths) == before
    else:
        assert response.status_code == 201
        assert response.json()["cart_reset_pending"] is True
        assert attempted == [m2_store_paths["orders"], m2_store_paths["carts"]]
        assert m2_store_paths["carts"].read_bytes() == before["carts"]
        assert len(OrderRepository().list_for_customer("customer-001")) == 1
        blocked = client.post(f"{CART}/items", headers=ada, json=FIRST)
        assert (blocked.status_code, blocked.json()) == (
            409, {"detail": "Cart checkout recovery required"})
        assert m2_store_paths["carts"].read_bytes() == before["carts"]
        for name in ("customers", "restaurants", "staff", "sessions"):
            assert m2_store_paths[name].read_bytes() == before[name]

    assert list(m2_store_paths["orders"].parent.glob(".*.tmp")) == []
    replay = client.post(CHECKOUT, headers=ada, json=attempt)
    assert replay.status_code == (201 if failed_store == "orders" else 200)
    assert replay.json()["cart_reset_pending"] is False
    saved = OrderRepository(m2_store_paths["orders"]).list_for_customer("customer-001")
    assert len(saved) == 1 and saved[0].id == replay.json()["order"]["id"]
    cleared = CartRepository(m2_store_paths["carts"]).get_cart("customer-001")
    assert (cleared.id, cleared.revision, cleared.items, cleared.restaurant_id) == (
        cart["id"], cart["revision"] + 1, [], None)


@pytest.mark.parametrize("store,repository_type", [
    ("restaurants", RestaurantRepository),
    ("customers", CustomerRepository),
    ("carts", CartRepository),
    ("orders", OrderRepository),
    ("staff", StaffRepository),
    ("sessions", SessionRepository),
])
def test_fresh_repository_configuration_uses_only_disposable_store(
        m2_store_paths, tmp_path, store, repository_type):
    repository = repository_type()
    assert repository.path == m2_store_paths[store]
    assert repository.path.parent == tmp_path
    assert repository.path.resolve() != (
        Path(__file__).resolve().parents[1] / "data" / f"{store}.json").resolve()
