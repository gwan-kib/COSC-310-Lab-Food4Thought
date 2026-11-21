"""Verify Food4Thought's complete signed-in customer purchase across real HTTP layers.
All six JSON stores are isolated; tests check rules, authoritative totals, saved
receipts, restart behaviour and both checkout persistence-failure boundaries.
"""

import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.api.routes import carts, checkout, customers, order_details, order_history, restaurants
from app.main import app
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository


CART = "/customers/me/cart"
CHECKOUT = "/customers/me/checkout"
FIRST_ITEM = {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2}
SECOND_ITEM = {"restaurant_id": "restaurant-001", "item_id": "item-002", "quantity": 1}
STORES = ("restaurants", "customers", "carts", "orders", "staff", "sessions")


@pytest.fixture
def client(auth_accounts, monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance


def _snapshot(paths):
    return {name: paths[name].read_bytes() for name in STORES}


def _register_and_sign_in(client, suffix):
    body = {
        "name": "Workflow Customer",
        "email": f"workflow-{suffix}@example.invalid",
        "delivery_address": "42 Integration Road",
        "password": "workflow-secret-123",
    }
    registered = client.post("/customers", json=body)
    assert registered.status_code == 201, registered.text
    account = registered.json()
    assert account["status"] == "active" and account["id"]
    logged_in = client.post("/auth/login", json={
        "email": body["email"], "password": body["password"],
    })
    assert logged_in.status_code == 200, logged_in.text
    assert logged_in.json()["role"] == "customer"
    return account, {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


def _ready_cart(client, headers):
    created = client.put(CART, headers=headers)
    assert created.status_code == 201, created.text
    added = client.post(f"{CART}/items", headers=headers, json=FIRST_ITEM)
    assert added.status_code == 200, added.text
    return added.json()


def _fresh_app(now):
    """Compose the actual routers again, resolving repositories from saved disk paths."""
    fresh = FastAPI()
    for router in (restaurants.router, customers.router, carts.router, checkout.router,
                   order_history.router, order_details.router):
        fresh.include_router(router)
    fresh.dependency_overrides[get_now] = lambda: now
    return fresh


def test_registration_to_menu_cart_checkout_and_reloaded_order(
        client, auth_accounts, m2_store_paths):
    account, headers = _register_and_sign_in(client, "purchase")

    listing = client.get("/restaurants")
    assert listing.status_code == 200
    assert any(place["id"] == "restaurant-001" for place in listing.json())
    menu = client.get("/restaurants/restaurant-001/menu")
    assert menu.status_code == 200
    assert {item["id"] for item in menu.json()["items"]} >= {"item-001", "item-002"}

    cart = _ready_cart(client, headers)
    cart_id = cart["id"]
    assert cart["customer_id"] == account["id"]
    assert cart["total"] == "25.00"

    quantity = client.patch(f"{CART}/items/item-001", headers=headers, json={"quantity": 3})
    assert quantity.status_code == 200
    next_item = client.post(f"{CART}/items", headers=headers, json=SECOND_ITEM)
    assert next_item.status_code == 200
    cart = next_item.json()
    assert cart["id"] == cart_id and cart["total"] == "51.50"

    # The browser's displayed quote must not become the purchase price.
    manager = auth_accounts.headers("restaurant_user")
    changed_price = client.patch("/restaurants/restaurant-001/menu/items/item-001",
                                 headers=manager, json={"price": "13.00"})
    assert changed_price.status_code == 200
    repriced = client.get(CART, headers=headers)
    assert repriced.status_code == 200
    assert repriced.json()["total"] == "53.00"
    assert repriced.json()["revision"] == cart["revision"]

    attempt = {"cart_id": cart_id, "cart_revision": cart["revision"]}
    response = client.post(CHECKOUT, headers=headers, json=attempt)
    assert response.status_code == 201, response.text
    assert response.json()["cart_reset_pending"] is False
    order = response.json()["order"]
    assert order["id"] and order["id"] != cart_id
    assert (order["customer_id"], order["restaurant_id"], order["source_cart_id"],
            order["source_cart_revision"]) == (
                account["id"], "restaurant-001", cart_id, cart["revision"])
    assert (order["delivery_address"], order["status"], order["subtotal"], order["total"]) == (
        "42 Integration Road", "placed", "53.00", "53.00")
    assert [(line["item_id"], line["quantity"], line["unit_price"], line["line_total"])
            for line in order["items"]] == [
                ("item-001", 3, "13.00", "39.00"),
                ("item-002", 1, "14.00", "14.00"),
            ]

    stored = json.loads(m2_store_paths["orders"].read_text(encoding="utf-8"))
    assert stored == [order]
    assert OrderRepository(m2_store_paths["orders"]).get_order(order["id"]).id == order["id"]
    reset = CartRepository(m2_store_paths["carts"]).get_cart(account["id"])
    assert (reset.id, reset.revision, reset.restaurant_id, reset.items) == (
        cart_id, cart["revision"] + 1, None, [])

    # Live profile/catalog updates cannot rewrite a historical order snapshot.
    assert client.patch("/customers/me", headers=headers,
                        json={"delivery_address": "99 Later Road"}).status_code == 200
    assert client.patch("/restaurants/restaurant-001/menu/items/item-001",
                        headers=manager, json={"name": "Renamed bowl", "price": "20.00"}
                        ).status_code == 200
    before_reads = _snapshot(m2_store_paths)

    with TestClient(_fresh_app(auth_accounts.now), raise_server_exceptions=False) as fresh:
        assert fresh.get(f"/customers/me/orders/{order['id']}", headers=headers).json() == order
        assert fresh.get("/customers/me/orders", headers=headers).json() == [order]
        replay = fresh.post(CHECKOUT, headers=headers, json=attempt)
        assert (replay.status_code, replay.json()) == (
            200, {"order": order, "cart_reset_pending": False})
        assert fresh.get(CART, headers=headers).json()["id"] == cart_id

    assert _snapshot(m2_store_paths) == before_reads
    assert len(json.loads(m2_store_paths["orders"].read_text())) == 1


@pytest.mark.parametrize("case,expected_status,expected_detail", [
    ("anonymous", 401, "Authentication required"),
    ("staff", 403, "Operation not permitted"),
    ("foreign_cart", 404, "Cart not found"),
    ("inactive", 403, "Customer is inactive"),
    ("mixed_restaurants", 409, "Cart belongs to another restaurant"),
    ("unavailable_at_checkout", 409, "Menu item is unavailable"),
    ("zero_quantity", 422, None),
    ("client_total", 422, None),
])
def test_checkout_rule_matrix_rejects_invalid_or_unauthorized_requests_without_writes(
        client, auth_accounts, m2_store_paths, case, expected_status, expected_detail):
    account, headers = _register_and_sign_in(client, case)
    cart = _ready_cart(client, headers)
    attempt = {"cart_id": cart["id"], "cart_revision": cart["revision"]}
    request_headers = headers
    endpoint = CHECKOUT
    body = attempt

    if case == "anonymous":
        request_headers = {}
    elif case == "staff":
        request_headers = auth_accounts.headers("restaurant_user")
    elif case == "foreign_cart":
        request_headers = auth_accounts.headers("customer_b")
    elif case == "inactive":
        assert client.post("/customers/me/deactivate", headers=headers).status_code == 200
    elif case == "mixed_restaurants":
        endpoint = f"{CART}/items"
        body = {"restaurant_id": "restaurant-002", "item_id": "item-003", "quantity": 1}
    elif case == "unavailable_at_checkout":
        manager = auth_accounts.headers("restaurant_user")
        assert client.patch("/restaurants/restaurant-001/menu/items/item-001",
                            headers=manager, json={"available": False}).status_code == 200
    elif case == "zero_quantity":
        endpoint = f"{CART}/items"
        body = {**FIRST_ITEM, "quantity": 0}
    elif case == "client_total":
        body = {**attempt, "total": "0.01"}

    before = _snapshot(m2_store_paths)
    result = client.post(endpoint, headers=request_headers, json=body)
    assert result.status_code == expected_status, result.text
    if expected_detail is not None:
        assert result.json() == {"detail": expected_detail}
    else:
        assert result.json()["detail"][0]["loc"][0] == "body"
    if case == "anonymous":
        assert result.headers["www-authenticate"] == "Bearer"
    assert _snapshot(m2_store_paths) == before
    assert client.get(CART, headers=headers).json()["id"] == cart["id"]
    assert OrderRepository().list_for_customer(account["id"]) == []


@pytest.mark.parametrize("failed_store", ["orders", "carts"])
def test_checkout_failure_boundaries_preserve_exact_recoverable_state(
        client, m2_store_paths, monkeypatch, failed_store):
    account, headers = _register_and_sign_in(client, f"failure-{failed_store}")
    cart = _ready_cart(client, headers)
    attempt = {"cart_id": cart["id"], "cart_revision": cart["revision"]}
    before = _snapshot(m2_store_paths)
    original_replace = os.replace

    def fail_selected_store(source, destination):
        if destination == m2_store_paths[failed_store]:
            raise OSError("simulated failed atomic replacement")
        return original_replace(source, destination)

    with monkeypatch.context() as failing:
        failing.setattr(os, "replace", fail_selected_store)
        first = client.post(CHECKOUT, headers=headers, json=attempt)

    if failed_store == "orders":
        assert (first.status_code, first.json()) == (
            500, {"detail": "Checkout data is unavailable"})
        assert _snapshot(m2_store_paths) == before
        assert OrderRepository().list_for_customer(account["id"]) == []
    else:
        assert first.status_code == 201
        assert first.json()["cart_reset_pending"] is True
        saved_order = first.json()["order"]
        assert m2_store_paths["carts"].read_bytes() == before["carts"]
        assert len(OrderRepository().list_for_customer(account["id"])) == 1
        for name in ("customers", "restaurants", "staff", "sessions"):
            assert m2_store_paths[name].read_bytes() == before[name]
        denied = client.post(f"{CART}/items", headers=headers, json=SECOND_ITEM)
        assert (denied.status_code, denied.json()) == (
            409, {"detail": "Cart checkout recovery required"})

    recovered = client.post(CHECKOUT, headers=headers, json=attempt)
    assert recovered.status_code == (201 if failed_store == "orders" else 200)
    assert recovered.json()["cart_reset_pending"] is False
    if failed_store == "carts":
        assert recovered.json()["order"] == saved_order
    assert len(OrderRepository().list_for_customer(account["id"])) == 1
    reset = CartRepository().get_cart(account["id"])
    assert (reset.id, reset.revision, reset.restaurant_id, reset.items) == (
        cart["id"], cart["revision"] + 1, None, [])
    assert list(m2_store_paths["orders"].parent.glob(".*.tmp")) == []
