"""Verify issue #89 through Food4Thought's real auth, cart and JSON storage layers.
Cover idempotent clearing, denied requests, failed writes and checkout recovery
using disposable stores, including fresh service/repository reads after mutations.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.api.routes.carts import get_cart_service
from app.core.storage import StorageFailure
from app.main import app
from app.repositories.cart import CartRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.schemas.customer import Principal
from app.schemas.order import CheckoutRequest
from app.services.cart import CustomerInactiveError, CustomerNotFoundError
from app.services.catalog import RestaurantCatalog
from app.services.checkout import CheckoutService
from app.services.customer import CustomerService

CART = "/customers/me/cart"
ITEMS = f"{CART}/items"


@pytest.fixture
def client(auth_accounts, monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    with TestClient(app, headers=auth_accounts.headers("customer_a")) as client:
        yield client


def fill_cart(client, headers=None):
    assert client.put(CART, headers=headers).status_code in (200, 201)
    for item_id, quantity in [("item-001", 2), ("item-002", 1)]:
        response = client.post(ITEMS, headers=headers, json={
            "restaurant_id": "restaurant-001", "item_id": item_id, "quantity": quantity})
        assert response.status_code == 200
    return response.json()


def snapshot(paths):
    return {name: path.read_bytes() if path.exists() else None for name, path in paths.items()}


def checkout_service():
    return CheckoutService(CustomerService(CustomerRepository()).active_customer_for,
                           CartRepository(), RestaurantCatalog(), OrderRepository())


def test_clear_saves_one_complete_empty_cart_then_repeats_without_writing(
        client, m2_store_paths, auth_accounts, monkeypatch):
    original = fill_cart(client)
    other_headers = auth_accounts.headers("customer_b")
    other = fill_cart(client, other_headers)
    before = snapshot(m2_store_paths)
    replacements = []
    from app.core.json_file import os
    real_replace = os.replace

    def record_replace(source, destination):
        # Observe actual atomic replacements and the complete JSON being persisted.
        replacements.append(json.loads(source.read_text(encoding="utf-8")))
        return real_replace(source, destination)

    monkeypatch.setattr("app.core.json_file.os.replace", record_replace)
    first = client.delete(ITEMS)
    assert first.status_code == 200
    assert first.json() == {
        "id": original["id"], "customer_id": "customer-001", "revision": 3,
        "restaurant_id": None, "items": [], "subtotal": "0.00", "total": "0.00",
        "checkout_order_id": None,
    }
    stored = CartRepository().get_cart("customer-001")
    assert stored.model_dump() == {
        "id": original["id"], "customer_id": "customer-001", "revision": 3,
        "restaurant_id": None, "items": [],
    }
    after = snapshot(m2_store_paths)
    second = client.delete(ITEMS)
    assert second.status_code == 200 and second.json() == first.json()
    assert snapshot(m2_store_paths) == after
    assert len(replacements) == 1
    assert next(c for c in replacements[0] if c["id"] == original["id"]) == stored.model_dump()
    assert get_cart_service().get_cart("customer-001").model_dump() == first.json()
    with TestClient(app, headers=auth_accounts.headers("customer_a")) as restarted_client:
        assert restarted_client.get(CART).json() == first.json()
    assert client.get(CART, headers=other_headers).json() == other
    assert {key: value for key, value in after.items() if key != "carts"} == {
        key: value for key, value in before.items() if key != "carts"}


def test_clear_of_initial_empty_cart_is_a_no_write(client, m2_store_paths, monkeypatch):
    original = client.put(CART).json()
    before = snapshot(m2_store_paths)

    def forbidden_save(*args):
        pytest.fail("Clearing an empty cart must not attempt a save")

    monkeypatch.setattr(CartRepository, "save_cart", forbidden_save)
    response = client.delete(ITEMS)
    assert response.status_code == 200 and response.json() == original
    assert snapshot(m2_store_paths) == before


def test_clear_releases_restaurant_and_allows_a_new_selection(client):
    original = fill_cart(client)
    assert client.delete(ITEMS).status_code == 200
    added = client.post(ITEMS, json={
        "restaurant_id": "restaurant-002", "item_id": "item-003", "quantity": 1})
    assert added.status_code == 200
    assert (added.json()["id"], added.json()["restaurant_id"], added.json()["revision"]) == (
        original["id"], "restaurant-002", 4)


def test_clear_missing_cart_does_not_create_one_or_touch_another_customer(
        client, auth_accounts, m2_store_paths):
    fill_cart(client, auth_accounts.headers("customer_b"))
    before = snapshot(m2_store_paths)
    response = client.delete(ITEMS)
    assert (response.status_code, response.json()) == (404, {"detail": "Cart not found"})
    assert snapshot(m2_store_paths) == before


@pytest.mark.parametrize("identity", ["missing", "invalid", "expired", "unknown",
                                     "restaurant_user", "administrator", "inactive"])
def test_clear_denials_preserve_all_stores(client, auth_accounts, m2_store_paths, identity):
    fill_cart(client)
    if identity == "inactive":
        assert client.post("/customers/me/deactivate").status_code == 200
    if identity == "unknown":
        customers = json.loads(m2_store_paths["customers"].read_text(encoding="utf-8"))
        m2_store_paths["customers"].write_text(json.dumps(customers[1:]), encoding="utf-8")
    headers = {
        "missing": {"Authorization": ""},
        "invalid": {"Authorization": "Bearer invalid-token"},
        "expired": {"Authorization": f"Bearer {auth_accounts.expired_token}"},
    }.get(identity, auth_accounts.headers(identity if identity in (
        "restaurant_user", "administrator") else "customer_a"))
    before = snapshot(m2_store_paths)
    response = client.delete(ITEMS, headers=headers)
    expected = 403 if identity in ("restaurant_user", "administrator", "inactive") else 401
    detail = ("Customer is inactive" if identity == "inactive" else
              "Operation not permitted" if expected == 403 else "Authentication required")
    assert (response.status_code, response.json()) == (expected, {"detail": detail})
    if expected == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert snapshot(m2_store_paths) == before


def test_anonymous_clear_does_not_read_private_cart_storage(client, m2_store_paths):
    m2_store_paths["carts"].write_text("broken private store", encoding="utf-8")
    before = snapshot(m2_store_paths)
    response = client.delete(ITEMS, headers={"Authorization": ""})
    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
    assert snapshot(m2_store_paths) == before


def test_client_supplied_owner_cannot_clear_another_cart(client, auth_accounts, m2_store_paths):
    original = fill_cart(client)
    before = snapshot(m2_store_paths)
    response = client.request("DELETE", ITEMS, headers=auth_accounts.headers("customer_b"),
                              params={"customer_id": "customer-001", "cart_id": original["id"]},
                              json={"customer_id": "customer-001", "cart_id": original["id"]})
    assert (response.status_code, response.json()) == (404, {"detail": "Cart not found"})
    assert snapshot(m2_store_paths) == before


@pytest.mark.parametrize("missing", [False, True])
def test_service_rechecks_customer_state_after_route_precheck(
        client, m2_store_paths, missing):
    fill_cart(client)
    service = get_cart_service()
    if missing:
        m2_store_paths["customers"].write_text("[]", encoding="utf-8")
    else:
        assert client.post("/customers/me/deactivate").status_code == 200
    before = snapshot(m2_store_paths)
    with pytest.raises(CustomerNotFoundError if missing else CustomerInactiveError):
        service.clear_cart("customer-001")
    assert snapshot(m2_store_paths) == before


def test_clear_can_remove_unavailable_items(client, auth_accounts):
    fill_cart(client)
    updated = client.patch("/restaurants/restaurant-001/menu/items/item-001",
                           headers=auth_accounts.headers("restaurant_user"), json={"available": False})
    assert updated.status_code == 200
    response = client.delete(ITEMS)
    assert response.status_code == 200 and response.json()["items"] == []


@pytest.mark.parametrize("store", ["carts", "orders", "restaurants"])
@pytest.mark.parametrize("damage", ["missing", "invalid_json"])
def test_clear_storage_errors_are_generic_and_preserve_records(
        client, m2_store_paths, store, damage):
    fill_cart(client)
    if damage == "missing":
        m2_store_paths[store].unlink()
    else:
        m2_store_paths[store].write_text("invalid json", encoding="utf-8")
    before = snapshot(m2_store_paths)
    response = client.delete(ITEMS)
    detail = "Restaurant data is unavailable" if store == "restaurants" else "Cart data is unavailable"
    assert (response.status_code, response.json()) == (500, {"detail": detail})
    assert snapshot(m2_store_paths) == before


@pytest.mark.parametrize("reference", ["restaurant", "item"])
def test_clear_rejects_missing_stored_references(client, m2_store_paths, reference):
    fill_cart(client)
    records = json.loads(m2_store_paths["carts"].read_text(encoding="utf-8"))
    if reference == "restaurant":
        records[0]["restaurant_id"] = "missing-restaurant"
    else:
        records[0]["items"][1]["item_id"] = "missing-item"
    m2_store_paths["carts"].write_text(json.dumps(records), encoding="utf-8")
    before = snapshot(m2_store_paths)
    response = client.delete(ITEMS)
    assert (response.status_code, response.json()) == (500, {"detail": "Cart data is unavailable"})
    assert snapshot(m2_store_paths) == before


def test_failed_clear_save_preserves_every_line_and_loaded_record(client, m2_store_paths, monkeypatch):
    original = fill_cart(client)
    service = get_cart_service()
    loaded = service.carts.get_cart("customer-001")
    original_record = loaded.model_copy(deep=True)
    monkeypatch.setattr(service.carts, "get_cart", lambda customer_id: loaded)
    monkeypatch.setitem(app.dependency_overrides, get_cart_service, lambda: service)
    before = snapshot(m2_store_paths)

    def fail_replace(*args):
        raise OSError("private path: disk full")

    monkeypatch.setattr("app.core.json_file.os.replace", fail_replace)
    response = client.delete(ITEMS)
    assert (response.status_code, response.json()) == (500, {"detail": "Cart data is unavailable"})
    assert snapshot(m2_store_paths) == before
    assert loaded == original_record == CartRepository().get_cart("customer-001")
    assert service.get_cart("customer-001").model_dump() == original


def test_pending_checkout_blocks_clear_until_real_receipt_replay_recovers(
        client, auth_accounts, m2_store_paths, monkeypatch):
    original = fill_cart(client)
    principal = Principal(account_id="customer-001", role="customer")
    request = CheckoutRequest(cart_id=original["id"], cart_revision=original["revision"])

    def fail_reset(*args):
        raise StorageFailure("cart reset unavailable")

    with monkeypatch.context() as failure:
        failure.setattr(CartRepository, "reset_after_order", fail_reset)
        purchase = checkout_service().checkout(principal, request)
    assert purchase.created and purchase.response.cart_reset_pending
    before = snapshot(m2_store_paths)
    blocked = client.delete(ITEMS)
    assert (blocked.status_code, blocked.json()) == (409, {"detail": "Cart checkout recovery required"})
    assert snapshot(m2_store_paths) == before
    assert client.get(CART).json()["checkout_order_id"] == purchase.response.order.id

    replay = checkout_service().checkout(principal, request)
    assert not replay.created and not replay.response.cart_reset_pending
    assert replay.response.order == purchase.response.order
    reset = client.get(CART).json()
    assert (reset["revision"], reset["items"]) == (3, [])
    assert client.delete(ITEMS).json() == reset
    fill_cart(client)
    assert client.delete(ITEMS).status_code == 200
    assert m2_store_paths["orders"].read_bytes() == before["orders"]
    assert OrderRepository().get_order(purchase.response.order.id) == purchase.response.order


def test_clear_rejects_a_restored_cart_whose_next_revision_was_already_purchased(
        client, m2_store_paths):
    fill_cart(client)
    old_cart_bytes = m2_store_paths["carts"].read_bytes()
    newer = client.post(ITEMS, json={
        "restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 1}).json()
    purchase = checkout_service().checkout(
        Principal(account_id="customer-001", role="customer"),
        CheckoutRequest(cart_id=newer["id"], cart_revision=newer["revision"]))
    assert purchase.created
    # Simulate mismatched backups: an older cart alongside newer durable receipts.
    m2_store_paths["carts"].write_bytes(old_cart_bytes)
    before = snapshot(m2_store_paths)

    response = client.delete(ITEMS)

    assert (response.status_code, response.json()) == (500, {"detail": "Cart data is unavailable"})
    assert snapshot(m2_store_paths) == before


def test_clear_openapi_documents_bearer_cart_response_and_errors(client):
    operation = client.get("/openapi.json").json()["paths"][ITEMS].get("delete")
    assert operation is not None
    assert operation["security"] == [{"HTTPBearer": []}]
    assert "requestBody" not in operation
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CartView"}
    for code in ("401", "403", "404", "409", "500"):
        assert operation["responses"][code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"}
