"""Exercise Food4Thought checkout through the authenticated HTTP application.
Use temporary stores to verify the purchase, replay and partial-write outcomes a customer sees.
"""

import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.core.workflow import workflow_lock
from app.main import app
from app.repositories.customer import CustomerRepository

CART = "/customers/me/cart"
CHECKOUT = "/customers/me/checkout"
MENU_ITEM = "/restaurants/restaurant-001/menu/items/item-001"
ITEM = {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2}


@pytest.fixture
def client(auth_accounts, monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    with TestClient(app, headers=auth_accounts.headers("customer_a")) as client:
        yield client


@pytest.fixture
def attempt(client):
    assert client.put(CART).status_code == 201
    added = client.post(f"{CART}/items", json=ITEM)
    assert added.status_code == 200
    cart = added.json()
    return {"cart_id": cart["id"], "cart_revision": cart["revision"]}


def store_bytes(paths):
    return {name: path.read_bytes() for name, path in paths.items()}


def test_checkout_prices_current_menu_and_replays_saved_snapshot_after_restart(
        client, attempt, auth_accounts):
    manager = auth_accounts.headers("restaurant_user")
    assert client.patch(MENU_ITEM, headers=manager, json={"price": "13.37"}).status_code == 200
    assert client.patch("/customers/me", json={"delivery_address": "Purchase address"}).status_code == 200
    purchase = client.post(CHECKOUT, json=attempt)
    assert purchase.status_code == 201
    order = purchase.json()["order"]
    assert order["id"]
    assert purchase.json() == {"order": {
        "id": order["id"], "customer_id": "customer-001", "restaurant_id": "restaurant-001",
        "restaurant_name": "Cedar Bowl", "source_cart_id": attempt["cart_id"],
        "source_cart_revision": attempt["cart_revision"], "delivery_address": "Purchase address",
        "status": "placed", "items": [{"item_id": "item-001", "name": "Vegetable bowl",
        "quantity": 2, "unit_price": "13.37", "line_total": "26.74"}],
        "subtotal": "26.74", "total": "26.74",
    }, "cart_reset_pending": False}
    reset = client.get(CART).json()
    assert (reset["id"], reset["revision"], reset["items"], reset["restaurant_id"]) == (
        attempt["cart_id"], attempt["cart_revision"] + 1, [], None)
    assert client.patch("/customers/me", json={"delivery_address": "Later address"}).status_code == 200
    assert client.patch(MENU_ITEM, headers=manager, json={"price": "20.00"}).status_code == 200
    new_cart = client.post(f"{CART}/items", json=ITEM)
    assert new_cart.status_code == 200

    from app.api.routes.checkout import router

    restarted = FastAPI()
    restarted.include_router(router)
    restarted.dependency_overrides[get_now] = lambda: auth_accounts.now
    with TestClient(restarted, headers=auth_accounts.headers("customer_a")) as fresh_client:
        replay = fresh_client.post(CHECKOUT, json=attempt)
    assert (replay.status_code, replay.json()) == (200, purchase.json())
    assert client.get(CART).json() == new_cart.json()
    assert client.get("/customers/me/orders").json() == [order]
    assert client.get(f"/customers/me/orders/{order['id']}").json() == order


@pytest.mark.parametrize("failed_store", ["orders", "carts"])
def test_write_failure_preserves_attempt_and_retry_buys_only_once(
        client, attempt, m2_store_paths, monkeypatch, failed_store):
    before = store_bytes(m2_store_paths)
    replace = os.replace

    def fail_selected_replace(source, destination):
        if destination == m2_store_paths[failed_store]:
            raise OSError("simulated failed replacement")
        return replace(source, destination)

    with monkeypatch.context() as failure:
        failure.setattr(os, "replace", fail_selected_replace)
        first = client.post(CHECKOUT, json=attempt)

    if failed_store == "orders":
        assert (first.status_code, first.json()) == (500, {"detail": "Checkout data is unavailable"})
        assert store_bytes(m2_store_paths) == before
        purchase = client.post(CHECKOUT, json=attempt)
        assert purchase.status_code == 201
    else:
        assert first.status_code == 201 and first.json()["cart_reset_pending"] is True
        assert m2_store_paths["carts"].read_bytes() == before["carts"]
        saved = first.json()["order"]
        assert client.get(CART).json()["checkout_order_id"] == saved["id"]
        blocked = client.delete(f"{CART}/items")
        assert (blocked.status_code, blocked.json()) == (409, {"detail": "Cart checkout recovery required"})
        purchase = client.post(CHECKOUT, json=attempt)
        assert (purchase.status_code, purchase.json()["order"]) == (200, saved)
    assert purchase.json()["cart_reset_pending"] is False
    assert json.loads(m2_store_paths["orders"].read_bytes()) == [purchase.json()["order"]]
    cart = client.get(CART).json()
    assert (cart["revision"], cart["items"]) == (attempt["cart_revision"] + 1, [])


@pytest.mark.parametrize("identity,status,detail", [
    ("anonymous", 401, "Authentication required"), ("expired", 401, "Authentication required"),
    ("restaurant_user", 403, "Operation not permitted"), ("administrator", 403, "Operation not permitted"),
    ("inactive", 403, "Customer is inactive"),
])
def test_identity_precedes_invalid_fields_and_private_reads(
        client, auth_accounts, m2_store_paths, identity, status, detail):
    if identity == "inactive":
        assert client.post("/customers/me/deactivate").status_code == 200
        headers = auth_accounts.headers("customer_a")
    elif identity == "anonymous":
        headers = {"Authorization": ""}
    elif identity == "expired":
        headers = {"Authorization": f"Bearer {auth_accounts.expired_token}"}
    else:
        headers = auth_accounts.headers(identity)
    m2_store_paths["orders"].write_text("{", encoding="utf-8")
    before = store_bytes(m2_store_paths)
    response = client.post(CHECKOUT, headers=headers, json={})
    assert (response.status_code, response.json()) == (status, {"detail": detail})
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("missing,status,detail", [
    (True, 401, "Authentication required"), (False, 403, "Customer is inactive")])
def test_customer_rechecked_under_checkout_lock(client, attempt, m2_store_paths, monkeypatch,
                                               missing, status, detail):
    real_read = CustomerRepository.get_customer

    def read_current_customer(repository, customer_id):
        customer = real_read(repository, customer_id)
        if workflow_lock.locked():
            return None if missing else customer.model_copy(update={"status": "inactive"})
        return customer

    monkeypatch.setattr(CustomerRepository, "get_customer", read_current_customer)
    before = store_bytes(m2_store_paths)
    response = client.post(CHECKOUT, json=attempt)
    assert (response.status_code, response.json()) == (status, {"detail": detail})
    if missing:
        assert response.headers["www-authenticate"] == "Bearer"
    assert store_bytes(m2_store_paths) == before


def test_foreign_cart_and_foreign_receipt_match_unknown_cart(client, attempt, auth_accounts, m2_store_paths):
    headers = auth_accounts.headers("customer_b")
    for purchased in (False, True):
        if purchased:
            assert client.post(CHECKOUT, json=attempt).status_code == 201
        before = store_bytes(m2_store_paths)
        for body in (attempt, {**attempt, "cart_id": "unknown"}):
            response = client.post(CHECKOUT, headers=headers, json=body)
            assert (response.status_code, response.json()) == (404, {"detail": "Cart not found"})
        assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("case,detail", [
    ("stale", "Cart revision changed"), ("empty", "Cart is empty"),
    ("unavailable", "Menu item is unavailable")])
def test_conflicts_leave_cart_and_order_store_unchanged(client, attempt, auth_accounts,
                                                      m2_store_paths, case, detail):
    if case == "stale":
        attempt["cart_revision"] -= 1
    elif case == "empty":
        cleared = client.delete(f"{CART}/items")
        assert cleared.status_code == 200
        attempt["cart_revision"] = cleared.json()["revision"]
    else:
        assert client.patch(MENU_ITEM, headers=auth_accounts.headers("restaurant_user"),
                            json={"available": False}).status_code == 200
    before = store_bytes(m2_store_paths)
    response = client.post(CHECKOUT, json=attempt)
    assert (response.status_code, response.json()) == (409, {"detail": detail})
    assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("invalid", [{"total": "0.00"}, {"customer_id": "customer-002"},
                                     {"cart_revision": -1}, {"cart_revision": True}, {"cart_id": ""}])
def test_invalid_purchase_fields_return_validation_errors_without_writes(client, attempt, m2_store_paths, invalid):
    before = store_bytes(m2_store_paths)
    response = client.post(CHECKOUT, json={**attempt, **invalid})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", *invalid]
    assert store_bytes(m2_store_paths) == before


def test_openapi_describes_checkout_and_replay(client):
    operation = client.get("/openapi.json").json()["paths"][CHECKOUT]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/CheckoutRequest")
    responses = operation["responses"]
    for code in ("200", "201"):
        assert responses[code]["content"]["application/json"]["schema"]["$ref"].endswith("/CheckoutResponse")
    for code in ("401", "403", "404", "409", "500"):
        assert responses[code]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
    assert "422" in responses
