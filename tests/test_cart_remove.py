"""Verify #88 removal through Food4Thought's auth, cart, catalog and JSON stores.
Exercise recovery, availability, persistence and denied requests using isolated
real stores, including the restaurant manager's availability API.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.main import app
from app.repositories.cart import CartDataError, CartRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.schemas.customer import Principal
from app.schemas.order import CheckoutRequest
from app.services.cart import CartService, CustomerInactiveError, CustomerNotFoundError
from app.services.catalog import RestaurantCatalog
from app.services.checkout import CheckoutService
from app.services.customer import CustomerService
from contracts.auth import FIXED_NOW

CART = "/customers/me/cart"
ITEM = f"{CART}/items/item-001"
ADD = {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2}


@pytest.fixture
def client(auth_accounts):
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_now, None)


@pytest.fixture
def ada(auth_accounts):
    return auth_accounts.headers("customer_a")


@pytest.fixture
def filled(client, ada):
    assert client.put(CART, headers=ada).status_code == 201
    response = client.post(f"{CART}/items", headers=ada, json=ADD)
    assert response.status_code == 200
    return response.json()


def _stores(paths):
    return {name: path.read_bytes() for name, path in paths.items()}


def _service():
    return CartService(CartRepository(), CustomerRepository(),
                       RestaurantCatalog(), OrderRepository())


def test_remove_one_then_last_line_reload_and_rebind_restaurant(client, ada, filled, m2_store_paths):
    second = client.post(f"{CART}/items", headers=ada,
                         json={**ADD, "item_id": "item-002", "quantity": 3})
    assert second.status_code == 200
    other_stores = {name: data for name, data in _stores(m2_store_paths).items() if name != "carts"}

    response = client.delete(ITEM, headers=ada)

    assert response.status_code == 200
    remaining = response.json()
    assert remaining == {
        "id": filled["id"], "customer_id": "customer-001", "revision": 3,
        "restaurant_id": "restaurant-001", "checkout_order_id": None,
        "items": [{"item_id": "item-002", "name": "Chicken udon", "quantity": 3,
                   "unit_price": "14.00", "line_total": "42.00", "available": True}],
        "subtotal": "42.00", "total": "42.00",
    }
    assert _service().get_cart("customer-001").model_dump() == remaining

    response = client.delete(f"{CART}/items/item-002", headers=ada)
    assert response.status_code == 200
    empty = response.json()
    assert empty == {**remaining, "items": [], "restaurant_id": None,
                     "revision": 4, "subtotal": "0.00", "total": "0.00"}
    assert _service().get_cart("customer-001").model_dump() == empty

    added = client.post(f"{CART}/items", headers=ada,
                        json={"restaurant_id": "restaurant-002", "item_id": "item-003", "quantity": 2})
    assert added.status_code == 200
    assert (added.json()["id"], added.json()["restaurant_id"], added.json()["revision"],
            added.json()["total"]) == (filled["id"], "restaurant-002", 5, "30.00")
    assert _service().get_cart("customer-001").model_dump() == added.json()
    assert {name: data for name, data in _stores(m2_store_paths).items() if name != "carts"} == other_stores


def test_removal_reprices_remaining_lines_from_current_menu(client, ada, filled, m2_store_paths):
    assert client.post(f"{CART}/items", headers=ada,
                       json={**ADD, "item_id": "item-002", "quantity": 3}).status_code == 200
    restaurants = json.loads(m2_store_paths["restaurants"].read_text())
    restaurants[0]["menu_items"][1]["price"] = "10.01"
    m2_store_paths["restaurants"].write_text(json.dumps(restaurants), encoding="utf-8")

    response = client.delete(ITEM, headers=ada)

    assert response.status_code == 200
    body = response.json()
    assert (body["items"][0]["unit_price"], body["items"][0]["line_total"],
            body["subtotal"], body["total"]) == ("10.01", "30.03", "30.03", "30.03")
    assert body["revision"] == 3


@pytest.mark.parametrize("has_cart", [False, True])
def test_missing_cart_or_line_is_404_without_writes(client, ada, m2_store_paths, has_cart):
    if has_cart:
        assert client.put(CART, headers=ada).status_code == 201
    before = _stores(m2_store_paths)

    response = client.delete(ITEM, headers=ada)

    assert (response.status_code, response.json()) == (
        404, {"detail": "Cart item not found" if has_cart else "Cart not found"})
    assert _stores(m2_store_paths) == before


@pytest.mark.parametrize("item_id", ["item-404", "item-003", "not-a-uuid", "%20"])
def test_line_ids_are_scoped_to_own_cart(client, ada, filled, m2_store_paths, item_id):
    before = _stores(m2_store_paths)
    response = client.delete(f"{CART}/items/{item_id}", headers=ada)
    assert (response.status_code, response.json()) == (404, {"detail": "Cart item not found"})
    assert _stores(m2_store_paths) == before


def test_repeated_removal_is_404_and_keeps_revision(client, ada, filled, m2_store_paths):
    assert client.delete(ITEM, headers=ada).status_code == 200
    before = _stores(m2_store_paths)
    response = client.delete(ITEM, headers=ada)
    assert (response.status_code, response.json()) == (404, {"detail": "Cart item not found"})
    assert _stores(m2_store_paths) == before
    assert CartRepository().get_cart("customer-001").revision == 2


@pytest.mark.parametrize("identity", ["anonymous", "invalid", "expired", "restaurant_user", "administrator"])
def test_remove_rejects_unpermitted_identity_without_writes(
    client, filled, auth_accounts, m2_store_paths, identity
):
    headers = {} if identity == "anonymous" else (
        {"Authorization": "Bearer unknown"} if identity == "invalid" else
        {"Authorization": f"Bearer {auth_accounts.expired_token}"} if identity == "expired" else
        auth_accounts.headers(identity))
    before = _stores(m2_store_paths)

    response = client.delete(ITEM, headers=headers)

    if identity in ("restaurant_user", "administrator"):
        assert (response.status_code, response.json()) == (403, {"detail": "Operation not permitted"})
    else:
        assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
        assert response.headers["www-authenticate"] == "Bearer"
    assert _stores(m2_store_paths) == before


def test_other_customer_cannot_select_owners_cart_with_query_or_body(
    client, filled, auth_accounts, m2_store_paths
):
    before = _stores(m2_store_paths)
    response = client.request("DELETE", f"{ITEM}?customer_id=customer-001&cart_id={filled['id']}",
                              headers=auth_accounts.headers("customer_b"),
                              json={"customer_id": "customer-001", "cart_id": filled["id"]})
    assert (response.status_code, response.json()) == (404, {"detail": "Cart not found"})
    assert _stores(m2_store_paths) == before


def test_removal_only_changes_callers_cart_when_both_have_same_item(
    client, ada, filled, auth_accounts, m2_store_paths
):
    ben = auth_accounts.headers("customer_b")
    assert client.put(CART, headers=ben).status_code == 201
    assert client.post(f"{CART}/items", headers=ben, json=ADD).status_code == 200
    ada_before = CartRepository().get_cart("customer-001")

    response = client.delete(ITEM, headers=ben)

    assert response.status_code == 200 and response.json()["items"] == []
    assert response.json()["customer_id"] == "customer-002"
    assert CartRepository().get_cart("customer-001") == ada_before


def test_old_token_is_denied_after_deactivation(client, ada, filled, m2_store_paths):
    assert client.post("/customers/me/deactivate", headers=ada).status_code == 200
    before = _stores(m2_store_paths)
    response = client.delete(ITEM, headers=ada)
    assert (response.status_code, response.json()) == (403, {"detail": "Customer is inactive"})
    assert _stores(m2_store_paths) == before


def test_service_rechecks_current_customer_status(client, ada, filled, m2_store_paths):
    service = _service()
    assert client.post("/customers/me/deactivate", headers=ada).status_code == 200
    before = _stores(m2_store_paths)
    with pytest.raises(CustomerInactiveError):
        service.remove_item("customer-001", "item-001")
    assert _stores(m2_store_paths) == before


def test_service_rejects_unknown_customer(filled, m2_store_paths):
    before = _stores(m2_store_paths)
    with pytest.raises(CustomerNotFoundError):
        _service().remove_item("customer-404", "item-001")
    assert _stores(m2_store_paths) == before


@pytest.mark.parametrize(("remove_id", "last_line", "expected_total"), [
    ("item-001", False, "14.00"), ("item-002", False, "25.00"), ("item-001", True, "0.00"),
])
def test_unavailable_line_can_be_removed_or_remain_in_totals(
    client, ada, filled, auth_accounts, remove_id, last_line, expected_total
):
    if not last_line:
        assert client.post(f"{CART}/items", headers=ada,
                           json={**ADD, "item_id": "item-002", "quantity": 1}).status_code == 200
    for item_id in ("item-001", "item-002"):
        disabled = client.patch(f"/restaurants/restaurant-001/menu/items/{item_id}",
                                headers=auth_accounts.headers("restaurant_user"), json={"available": False})
        assert disabled.status_code == 200 and disabled.json()["available"] is False

    response = client.delete(f"{CART}/items/{remove_id}", headers=ada)

    assert response.status_code == 200
    if last_line:
        assert response.json()["items"] == [] and response.json()["restaurant_id"] is None
    else:
        assert response.json()["items"][0]["available"] is False
    assert response.json()["total"] == expected_total
    assert _service().get_cart("customer-001").model_dump() == response.json()


@pytest.mark.parametrize("store", ["carts", "orders", "restaurants"])
def test_corrupt_required_store_never_returns_success_or_changes_state(client, ada, filled, m2_store_paths, store):
    m2_store_paths[store].write_text("not json", encoding="utf-8")
    before = _stores(m2_store_paths)
    response = client.delete(ITEM, headers=ada)
    assert response.status_code == 500
    assert response.json() == {"detail": "Restaurant data is unavailable" if store == "restaurants"
                              else "Cart data is unavailable"}
    assert _stores(m2_store_paths) == before


@pytest.mark.parametrize("missing", ["removed_item", "remaining_item", "restaurant"])
def test_missing_stored_references_are_not_silently_repaired(client, ada, filled, m2_store_paths, missing):
    assert client.post(f"{CART}/items", headers=ada,
                       json={**ADD, "item_id": "item-002", "quantity": 1}).status_code == 200
    restaurants = json.loads(m2_store_paths["restaurants"].read_text())
    if missing == "restaurant":
        restaurants.pop(0)
    else:
        restaurants[0]["menu_items"].pop(0 if missing == "removed_item" else 1)
    m2_store_paths["restaurants"].write_text(json.dumps(restaurants), encoding="utf-8")
    before = _stores(m2_store_paths)

    response = client.delete(ITEM, headers=ada)

    assert (response.status_code, response.json()) == (500, {"detail": "Cart data is unavailable"})
    assert _stores(m2_store_paths) == before


def test_failed_atomic_save_keeps_previous_cart_and_no_temporary_file(
    client, ada, filled, m2_store_paths, monkeypatch
):
    before = _stores(m2_store_paths)
    files_before = set(m2_store_paths["carts"].parent.iterdir())

    def failed_replace(*_args):
        raise OSError("test-only private disk failure")

    with monkeypatch.context() as failure:
        failure.setattr("app.core.json_file.os.replace", failed_replace)
        response = client.delete(ITEM, headers=ada)

    assert (response.status_code, response.json()) == (500, {"detail": "Cart data is unavailable"})
    assert _stores(m2_store_paths) == before
    assert set(m2_store_paths["carts"].parent.iterdir()) == files_before
    assert _service().get_cart("customer-001").model_dump() == filled


def test_purchased_revision_blocks_removal_until_real_checkout_recovery(
    client, ada, filled, m2_store_paths, monkeypatch
):
    principal = Principal(account_id="customer-001", role="customer")
    request = CheckoutRequest(cart_id=filled["id"], cart_revision=filled["revision"])

    def checkout():
        return CheckoutService(CustomerService(CustomerRepository()).active_customer_for,
                               CartRepository(), RestaurantCatalog(), OrderRepository())

    def failed_reset(*_args):
        raise CartDataError("test-only reset failure")

    with monkeypatch.context() as failure:
        failure.setattr(CartRepository, "reset_after_order", failed_reset)
        purchase = checkout().checkout(principal, request)
    assert purchase.response.cart_reset_pending is True
    before = _stores(m2_store_paths)

    response = client.delete(ITEM, headers=ada)

    assert (response.status_code, response.json()) == (409, {"detail": "Cart checkout recovery required"})
    assert _stores(m2_store_paths) == before
    recovered = checkout().checkout(principal, request)
    assert recovered.created is False and recovered.response.cart_reset_pending is False
    assert recovered.response.order == purchase.response.order
    assert client.post(f"{CART}/items", headers=ada, json=ADD).status_code == 200
    assert client.delete(ITEM, headers=ada).status_code == 200
    assert m2_store_paths["orders"].read_bytes() == before["orders"]


def test_remove_openapi_describes_bearer_cart_response_and_errors(client):
    operation = client.get("/openapi.json").json()["paths"][f"{CART}/items/{{item_id}}"]["delete"]
    assert "requestBody" not in operation
    assert operation["security"] == [{"HTTPBearer": []}]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CartView"}
    assert {"401", "403", "404", "409", "500"} <= operation["responses"].keys()
    assert "Cart item not found" in operation["responses"]["404"]["description"]
