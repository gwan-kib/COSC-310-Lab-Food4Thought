"""Exercise Food4Thought's protected cart API and account deactivation end to end.
Covers #83 (deactivate), #84 (cart routes need a customer token), #85 (create or read
the cart), #86 (add an item) and #90 (cart contents and backend totals), using real
routes, services and isolated stores with a fixed clock.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.api.routes.carts import get_cart_service
from app.main import app
from app.repositories.cart import CartRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.services.cart import CartService
from app.services.catalog import RestaurantCatalog
from contracts.auth import FIXED_NOW
from contracts.m2 import CatalogItem, FakeCatalog

ADD = {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2}


@pytest.fixture
def client(m2_store_paths):
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    yield TestClient(app)
    app.dependency_overrides.pop(get_now, None)


@pytest.fixture
def ada(auth_accounts):
    return auth_accounts.headers("customer_a")


def _stores(paths):
    return {name: paths[name].read_bytes() for name in ("customers", "carts")}


# --- #84 protection ------------------------------------------------------------------------

@pytest.mark.parametrize(("method", "path"), [
    ("put", "/customers/me/cart"), ("get", "/customers/me/cart"),
    ("post", "/customers/me/cart/items"), ("post", "/customers/me/deactivate"),
])
def test_cart_and_account_routes_require_a_customer_token(client, m2_store_paths, auth_accounts, method, path):
    before = _stores(m2_store_paths)
    anonymous = client.request(method, path, json=ADD)
    staff = client.request(method, path, json=ADD, headers=auth_accounts.headers("restaurant_user"))

    assert (anonymous.status_code, anonymous.headers["www-authenticate"]) == (401, "Bearer")
    assert (staff.status_code, staff.json()) == (403, {"detail": "Operation not permitted"})
    assert _stores(m2_store_paths) == before


# --- #85 create or retrieve -------------------------------------------------------------------

def test_put_creates_then_returns_the_same_cart(client, ada):
    first = client.put("/customers/me/cart", headers=ada)
    second = client.put("/customers/me/cart", headers=ada)

    assert first.status_code == 201 and second.status_code == 200
    assert first.json() == second.json()
    assert first.json() | {"id": "x"} == {
        "id": "x", "customer_id": "customer-001", "revision": 0, "restaurant_id": None,
        "items": [], "subtotal": "0.00", "total": "0.00", "checkout_order_id": None}


def test_get_before_create_is_404_and_writes_nothing(client, m2_store_paths, ada):
    before = _stores(m2_store_paths)
    response = client.get("/customers/me/cart", headers=ada)

    assert (response.status_code, response.json()) == (404, {"detail": "Cart not found"})
    assert _stores(m2_store_paths) == before


def test_each_customer_only_ever_sees_their_own_cart(client, auth_accounts, ada):
    client.put("/customers/me/cart", headers=ada)
    client.post("/customers/me/cart/items", headers=ada, json=ADD)
    ben = auth_accounts.headers("customer_b")

    assert client.get("/customers/me/cart", headers=ben).status_code == 404
    assert client.put("/customers/me/cart", headers=ben).json()["items"] == []


# --- #86 add item and #90 totals ----------------------------------------------------------------

def test_add_item_returns_backend_totals_that_persist(client, ada):
    client.put("/customers/me/cart", headers=ada)
    client.post("/customers/me/cart/items", headers=ada, json=ADD)
    response = client.post("/customers/me/cart/items", headers=ada,
                           json={"restaurant_id": "restaurant-001", "item_id": "item-002", "quantity": 1})

    assert response.status_code == 200
    body = response.json()
    assert [(i["item_id"], i["quantity"], i["line_total"]) for i in body["items"]] == [
        ("item-001", 2, "25.00"), ("item-002", 1, "14.00")]
    assert (body["subtotal"], body["total"], body["revision"]) == ("39.00", "39.00", 2)
    assert client.get("/customers/me/cart", headers=ada).json() == body


@pytest.mark.parametrize(("body", "status", "detail"), [
    ({"restaurant_id": "restaurant-404", "item_id": "item-001", "quantity": 1}, 404, "Restaurant not found"),
    ({"restaurant_id": "restaurant-001", "item_id": "item-404", "quantity": 1}, 404, "Menu item not found"),
    ({"restaurant_id": "restaurant-001", "item_id": "item-003", "quantity": 1}, 404, "Menu item not found"),
])
def test_missing_or_wrong_parent_items_are_404_without_writes(client, m2_store_paths, ada, body, status, detail):
    client.put("/customers/me/cart", headers=ada)
    before = _stores(m2_store_paths)
    response = client.post("/customers/me/cart/items", headers=ada, json=body)

    assert (response.status_code, response.json()) == (status, {"detail": detail})
    assert _stores(m2_store_paths) == before


def test_mixing_restaurants_is_409_without_writes(client, m2_store_paths, ada):
    client.put("/customers/me/cart", headers=ada)
    client.post("/customers/me/cart/items", headers=ada, json=ADD)
    before = _stores(m2_store_paths)
    response = client.post("/customers/me/cart/items", headers=ada,
                           json={"restaurant_id": "restaurant-002", "item_id": "item-003", "quantity": 1})

    assert (response.status_code, response.json()) == (409, {"detail": "Cart belongs to another restaurant"})
    assert _stores(m2_store_paths) == before


def test_unavailable_item_is_409_without_writes(client, m2_store_paths, ada):
    # Menu availability (#94) is not on main yet, so supply it through the catalog seam.
    restaurant = RestaurantCatalog().get_restaurant("restaurant-001")
    item = CatalogItem(id="item-001", name="Vegetable bowl", description="Seasonal",
                       price="12.50", available=False)
    app.dependency_overrides[get_cart_service] = lambda: CartService(
        carts=CartRepository(), customers=CustomerRepository(), receipts=OrderRepository(),
        catalog=FakeCatalog([restaurant], {("restaurant-001", "item-001"): item}))
    try:
        client.put("/customers/me/cart", headers=ada)
        before = _stores(m2_store_paths)
        response = client.post("/customers/me/cart/items", headers=ada, json=ADD)
    finally:
        app.dependency_overrides.pop(get_cart_service, None)

    assert (response.status_code, response.json()) == (409, {"detail": "Menu item is unavailable"})
    assert _stores(m2_store_paths) == before


def test_add_before_creating_a_cart_is_404(client, m2_store_paths, ada):
    response = client.post("/customers/me/cart/items", headers=ada, json=ADD)
    assert (response.status_code, response.json()) == (404, {"detail": "Cart not found"})


@pytest.mark.parametrize("change", [
    {"quantity": 0}, {"quantity": -1}, {"quantity": 1.5}, {"quantity": "2"}, {"quantity": True},
    {"price": "0.01"}, {"total": "0.00"}, {"customer_id": "customer-002"},
])
def test_invalid_quantities_and_client_prices_are_422_without_writes(client, m2_store_paths, ada, change):
    client.put("/customers/me/cart", headers=ada)
    before = _stores(m2_store_paths)
    response = client.post("/customers/me/cart/items", headers=ada, json={**ADD, **change})

    assert response.status_code == 422
    assert _stores(m2_store_paths) == before


# --- #83 deactivate --------------------------------------------------------------------------------

def test_deactivate_keeps_the_account_and_cart_and_is_repeatable(client, m2_store_paths, ada):
    client.put("/customers/me/cart", headers=ada)
    client.post("/customers/me/cart/items", headers=ada, json=ADD)

    first = client.post("/customers/me/deactivate", headers=ada)
    second = client.post("/customers/me/deactivate", headers=ada)

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "inactive"
    assert first.json()["id"] == "customer-001"
    assert client.get("/customers/me", headers=ada).json()["status"] == "inactive"
    assert client.get("/customers/me/cart", headers=ada).json()["total"] == "25.00"


def test_old_token_cannot_change_the_cart_after_deactivation(client, m2_store_paths, ada):
    client.put("/customers/me/cart", headers=ada)
    client.post("/customers/me/deactivate", headers=ada)
    before = _stores(m2_store_paths)

    for method, path, body in [("put", "/customers/me/cart", None),
                               ("post", "/customers/me/cart/items", ADD),
                               ("post", "/customers/me/cart/items", {**ADD, "quantity": 0}),
                               ("patch", "/customers/me", {"name": "New"})]:
        response = client.request(method, path, headers=ada, json=body)
        assert (response.status_code, response.json()) == (403, {"detail": "Customer is inactive"}), path
    assert _stores(m2_store_paths) == before


def test_deactivated_customer_can_still_sign_in_and_read(client, auth_accounts, ada):
    client.post("/customers/me/deactivate", headers=ada)
    login = client.post("/auth/login", json={"email": "ada@example.invalid",
                                             "password": auth_accounts.accounts["customer_a"].password})

    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert login.status_code == 200
    assert client.get("/customers/me", headers=headers).json()["status"] == "inactive"
