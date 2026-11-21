"""Exercise Food4Thought's protected cart API and account deactivation end to end.
Covers #83 (deactivate), #84 (cart routes need a customer token), #85 (create or read
the cart), #86 (add an item), #87 (set its quantity) and #90 (cart contents and backend totals), using real
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
from app.schemas.customer import Principal
from app.schemas.order import CheckoutRequest
from app.services.cart import CartService
from app.services.checkout import CheckoutService
from app.services.catalog import RestaurantCatalog
from app.services.customer import CustomerInactiveError, CustomerService
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


# --- PR #115 review regressions -------------------------------------------------------------

def test_put_cart_documents_the_cart_body_for_both_200_and_201(client):
    responses = client.get("/openapi.json").json()["paths"]["/customers/me/cart"]["put"]["responses"]
    for code in ("200", "201"):
        schema = responses[code]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/CartView"}, code


def test_profile_update_after_checkout_keeps_ids_carts_and_the_order_snapshot(client, m2_store_paths, auth_accounts, ada):
    ben = auth_accounts.headers("customer_b")
    cart = client.put("/customers/me/cart", headers=ada).json()
    client.put("/customers/me/cart", headers=ben)
    cart = client.post("/customers/me/cart/items", headers=ada, json=ADD).json()
    assert client.get("/customers/me/cart", headers=ben).json()["items"] == []

    order = _real_checkout().checkout(ADA_PRINCIPAL, CheckoutRequest(
        cart_id=cart["id"], cart_revision=cart["revision"])).response.order
    orders_before = m2_store_paths["orders"].read_bytes()

    updated = client.patch("/customers/me", headers=ada,
                           json={"name": "Ada Renamed", "delivery_address": "9 Moved Street"})

    assert updated.status_code == 200 and updated.json()["id"] == "customer-001"
    assert client.get("/customers/me/cart", headers=ada).json()["id"] == cart["id"]
    assert m2_store_paths["orders"].read_bytes() == orders_before
    assert OrderRepository().get_order(order.id).delivery_address == "101 Example Street, Kelowna, BC"


def test_staff_record_claiming_the_customer_role_cannot_reach_the_cart(client, m2_store_paths, auth_accounts):
    staff = json.loads(m2_store_paths["staff"].read_text(encoding="utf-8"))
    staff[0]["role"] = "customer"
    m2_store_paths["staff"].write_text(json.dumps(staff), encoding="utf-8")
    before = {name: m2_store_paths[name].read_bytes()
              for name in ("customers", "carts", "staff", "sessions")}

    response = client.put("/customers/me/cart", headers=auth_accounts.headers("restaurant_user"))

    assert (response.status_code, response.json()) == (500, {"detail": "Authentication data is unavailable"})
    assert {name: m2_store_paths[name].read_bytes() for name in before} == before


# --- PR #115 second review (gwan-kib) -------------------------------------------------------

ADA_PRINCIPAL = Principal(account_id="customer-001", role="customer")


def _real_checkout():
    # The composition the checkout route must use: the stored customer, rechecked
    # for active status inside checkout's workflow lock.
    return CheckoutService(CustomerService(CustomerRepository()).active_customer_for,
                           carts=CartRepository(), catalog=RestaurantCatalog(), orders=OrderRepository())


def test_checkout_rejects_a_customer_deactivated_after_signing_in(client, m2_store_paths, auth_accounts, ada):
    # Sign in, fill the cart, then deactivate: the old token's route pre-check already
    # passed, so the authoritative check is the one inside checkout's lock.
    client.put("/customers/me/cart", headers=ada)
    cart = client.post("/customers/me/cart/items", headers=ada, json=ADD).json()
    assert client.post("/customers/me/deactivate", headers=ada).status_code == 200
    before = {name: m2_store_paths[name].read_bytes() for name in ("customers", "carts", "orders")}

    with pytest.raises(CustomerInactiveError):
        _real_checkout().checkout(ADA_PRINCIPAL, CheckoutRequest(cart_id=cart["id"],
                                                                 cart_revision=cart["revision"]))

    assert {name: m2_store_paths[name].read_bytes() for name in ("customers", "carts", "orders")} == before


def test_active_customer_resolver_returns_the_stored_customer_for_checkout(auth_accounts):
    customer = CustomerService(CustomerRepository()).active_customer_for(ADA_PRINCIPAL)
    assert (customer.id, customer.delivery_address) == ("customer-001", "101 Example Street, Kelowna, BC")


def test_cart_and_checkout_reprice_but_retry_keeps_the_saved_order(client, ada, auth_accounts):
    restaurant = "restaurant-001"
    manager = auth_accounts.headers("restaurant_user")

    def update_menu_item(item_id, **changes):
        response = client.patch(f"/restaurants/{restaurant}/menu/items/{item_id}",
                                headers=manager, json=changes)
        assert response.status_code == 200, response.text

    update_menu_item("item-001", name="Soup", price="10.00")
    update_menu_item("item-002", name="Bread", price="3.25")
    assert client.put("/customers/me/cart", headers=ada).status_code == 201
    for item, quantity in [("item-001", 2), ("item-002", 1)]:
        added = client.post("/customers/me/cart/items", headers=ada, json={
            "restaurant_id": restaurant, "item_id": item, "quantity": quantity,
        })
        assert added.status_code == 200

    cart = client.get("/customers/me/cart", headers=ada).json()
    assert (cart["subtotal"], cart["total"]) == ("23.25", "23.25")
    request = CheckoutRequest(cart_id=cart["id"], cart_revision=cart["revision"])

    update_menu_item("item-001", price="11.50")
    refreshed = client.get("/customers/me/cart", headers=ada).json()
    assert [line["line_total"] for line in refreshed["items"]] == ["23.00", "3.25"]
    assert (refreshed["subtotal"], refreshed["total"]) == ("26.25", "26.25")

    purchase = _real_checkout().checkout(ADA_PRINCIPAL, request)
    order = purchase.response.order
    assert purchase.created
    assert [(line.unit_price, line.line_total) for line in order.items] == [
        ("11.50", "23.00"), ("3.25", "3.25"),
    ]
    assert (order.subtotal, order.total) == ("26.25", "26.25")

    update_menu_item("item-001", price="14.00")
    retry = _real_checkout().checkout(ADA_PRINCIPAL, request)
    assert not retry.created
    assert retry.response.order == order


ITEM_URL = "/customers/me/cart/items/item-001"


@pytest.fixture
def two_line_cart(client, ada):
    assert client.put("/customers/me/cart", headers=ada).status_code == 201
    for line in (ADD, {**ADD, "item_id": "item-002", "quantity": 1}):
        response = client.post("/customers/me/cart/items", headers=ada, json=line)
        assert response.status_code == 200
    return response.json()


def test_quantity_patch_reprices_and_persists_only_the_selected_quantity(client, ada, two_line_cart):
    response = client.patch(ITEM_URL, headers=ada, json={"quantity": 3})
    assert response.status_code == 200
    original, sibling = two_line_cart["items"]
    assert response.json() == {
        **two_line_cart, "revision": two_line_cart["revision"] + 1,
        "items": [{**original, "quantity": 3, "line_total": "37.50"}, sibling],
        "subtotal": "51.50", "total": "51.50",
    }
    assert client.get("/customers/me/cart", headers=ada).json() == response.json()


def test_quantity_patch_noop_returns_current_price_without_saving(
    client, ada, auth_accounts, two_line_cart, monkeypatch
):
    updated = client.patch("/restaurants/restaurant-001/menu/items/item-001",
                           headers=auth_accounts.headers("restaurant_user"), json={"price": "10.25"})
    assert updated.status_code == 200
    monkeypatch.setattr(CartRepository, "save_cart", lambda *args: pytest.fail("unexpected cart save"))
    response = client.patch(ITEM_URL, headers=ada, json={"quantity": 2})
    assert response.status_code == 200
    assert response.json()["revision"] == two_line_cart["revision"]
    assert response.json()["total"] == "34.50"


@pytest.mark.parametrize("body", [
    {}, {"quantity": 0}, {"quantity": -1}, {"quantity": 2.0}, {"quantity": 1.5},
    {"quantity": "2"}, {"quantity": True}, {"quantity": None},
    {"quantity": 3, "customer_id": "customer-002"}, {"quantity": 3, "unit_price": "0.01"},
])
def test_quantity_patch_validates_body_before_mutation(client, ada, two_line_cart, m2_store_paths, body):
    before = m2_store_paths["carts"].read_bytes()
    response = client.patch(ITEM_URL, headers=ada, json=body)
    assert response.status_code == 422
    assert m2_store_paths["carts"].read_bytes() == before


def test_quantity_patch_protects_the_owners_cart(client, ada, auth_accounts, two_line_cart, m2_store_paths):
    before = m2_store_paths["carts"].read_bytes()
    for headers, status, detail in [
        ({}, 401, "Authentication required"),
        (auth_accounts.headers("restaurant_user"), 403, "Operation not permitted"),
        (auth_accounts.headers("customer_b"), 404, "Cart not found"),
    ]:
        result = client.patch(ITEM_URL, headers=headers, json={"quantity": 1})
        assert (result.status_code, result.json()) == (status, {"detail": detail})
    result = client.patch("/customers/me/cart/items/missing", headers=ada, json={"quantity": 1})
    assert (result.status_code, result.json()) == (404, {"detail": "Cart item not found"})
    assert client.post("/customers/me/deactivate", headers=ada).status_code == 200
    result = client.patch(ITEM_URL, headers=ada, json={"quantity": 0})
    assert (result.status_code, result.json()) == (403, {"detail": "Customer is inactive"})
    assert m2_store_paths["carts"].read_bytes() == before


def test_quantity_patch_rechecks_availability_even_for_a_noop(
    client, ada, auth_accounts, two_line_cart, m2_store_paths
):
    changed = client.patch("/restaurants/restaurant-001/menu/items/item-001",
                           headers=auth_accounts.headers("restaurant_user"), json={"available": False})
    assert changed.status_code == 200
    before = m2_store_paths["carts"].read_bytes()
    for quantity in (1, 2, 3):
        result = client.patch(ITEM_URL, headers=ada, json={"quantity": quantity})
        assert (result.status_code, result.json()) == (409, {"detail": "Menu item is unavailable"})
    assert m2_store_paths["carts"].read_bytes() == before


def test_quantity_patch_rejects_purchased_revision(client, ada, two_line_cart, m2_store_paths, monkeypatch):
    def fail_reset(*args):
        raise OSError("reset failed")

    monkeypatch.setattr(CartRepository, "reset_after_order", fail_reset)
    purchase = _real_checkout().checkout(ADA_PRINCIPAL, CheckoutRequest(
        cart_id=two_line_cart["id"], cart_revision=two_line_cart["revision"]))
    assert purchase.response.cart_reset_pending
    before = {name: m2_store_paths[name].read_bytes() for name in ("carts", "orders")}
    result = client.patch(ITEM_URL, headers=ada, json={"quantity": 2})
    assert (result.status_code, result.json()) == (409, {"detail": "Cart checkout recovery required"})
    assert {name: m2_store_paths[name].read_bytes() for name in before} == before


def test_quantity_patch_failed_replace_keeps_original_cart(client, ada, two_line_cart, m2_store_paths, monkeypatch):
    def fail_replace(*args):
        raise OSError("replace failed")

    before = m2_store_paths["carts"].read_bytes()
    monkeypatch.setattr("app.core.json_file.os.replace", fail_replace)
    result = client.patch(ITEM_URL, headers=ada, json={"quantity": 1})
    assert (result.status_code, result.json()) == (500, {"detail": "Cart data is unavailable"})
    assert m2_store_paths["carts"].read_bytes() == before
    assert client.get("/customers/me/cart", headers=ada).json() == two_line_cart
