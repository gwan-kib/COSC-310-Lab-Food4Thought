"""Check that Food4Thought protects every customer-specific endpoint end to end (#83, #84).
Real sign-in, cart, checkout and order routes run against isolated JSON stores: deactivation
blocks every write from an old token but keeps the account, cart and orders readable, and
anonymous callers, staff and other customers can never reach a customer's resources.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.main import app
from contracts.auth import FIXED_NOW

ADD = {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2}
ITEM = "/customers/me/cart/items/item-001"
STORES = ("customers", "sessions", "staff", "carts", "orders", "restaurants")

# Every customer-scoped operation, with a body that would be valid for a signed-in customer.
CUSTOMER_ENDPOINTS = [
    ("GET", "/customers/me", None),
    ("PATCH", "/customers/me", {"name": "New Name"}),
    ("POST", "/customers/me/deactivate", None),
    ("GET", "/customers/me/cart", None),
    ("PUT", "/customers/me/cart", None),
    ("POST", "/customers/me/cart/items", ADD),
    ("PATCH", ITEM, {"quantity": 1}),
    ("DELETE", ITEM, None),
    ("DELETE", "/customers/me/cart/items", None),
    ("POST", "/customers/me/checkout", {"cart_id": "cart-x", "cart_revision": 1}),
    ("GET", "/customers/me/orders", None),
    ("GET", "/customers/me/orders/order-x", None),
]
WRITES_DENIED_WHEN_INACTIVE = [e for e in CUSTOMER_ENDPOINTS
                               if e[1].startswith("/customers/me/c") and e[0] != "GET"]


@pytest.fixture
def client(m2_store_paths):
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    yield TestClient(app)
    app.dependency_overrides.pop(get_now, None)


def _call(client, method, path, body, headers):
    return client.request(method, path, json=body, headers=headers)


def _bytes(paths):
    return {store: paths[store].read_bytes() for store in STORES}


def _sign_in(client, auth_accounts, key):
    account = auth_accounts.accounts[key]
    response = client.post("/auth/login", json={"email": account.record.email,
                                                 "password": account.password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _buy_once_then_refill(client, headers):
    """Place one order, then put an item back in the cart; returns (order, cart)."""
    assert client.put("/customers/me/cart", headers=headers).status_code == 201
    cart = client.post("/customers/me/cart/items", headers=headers, json=ADD).json()
    purchase = client.post("/customers/me/checkout", headers=headers,
                           json={"cart_id": cart["id"], "cart_revision": cart["revision"]})
    assert purchase.status_code == 201
    refilled = client.post("/customers/me/cart/items", headers=headers, json=ADD)
    assert refilled.status_code == 200
    return purchase.json()["order"], refilled.json()


# --- #83: deactivation with a previously issued token ---------------------------------------

def test_deactivated_customer_keeps_records_but_every_write_is_refused(client, m2_store_paths, auth_accounts):
    old_token = _sign_in(client, auth_accounts, "customer_a")
    order, cart = _buy_once_then_refill(client, old_token)

    deactivated = client.post("/customers/me/deactivate", headers=old_token)
    assert deactivated.status_code == 200
    assert (deactivated.json()["id"], deactivated.json()["status"]) == ("customer-001", "inactive")
    before = _bytes(m2_store_paths)

    # The old token can no longer change the cart or check out, even with valid bodies.
    checkout = client.post("/customers/me/checkout", headers=old_token,
                           json={"cart_id": cart["id"], "cart_revision": cart["revision"]})
    assert (checkout.status_code, checkout.json()) == (403, {"detail": "Customer is inactive"})
    for method, path, body in WRITES_DENIED_WHEN_INACTIVE:
        response = _call(client, method, path, body, old_token)
        assert (response.status_code, response.json()) == (403, {"detail": "Customer is inactive"}), path
    assert _bytes(m2_store_paths) == before

    # Nothing was deleted: the same account, cart and order are still readable.
    assert client.get("/customers/me", headers=old_token).json()["id"] == "customer-001"
    kept = client.get("/customers/me/cart", headers=old_token)
    assert (kept.status_code, kept.json()["id"], kept.json()["items"]) == (200, cart["id"], cart["items"])
    assert [o["id"] for o in client.get("/customers/me/orders", headers=old_token).json()] == [order["id"]]
    assert client.get(f"/customers/me/orders/{order['id']}", headers=old_token).json() == order

    # Signing in again (a fresh token after the change was saved) is still refused at checkout.
    new_token = _sign_in(client, auth_accounts, "customer_a")
    again = client.post("/customers/me/checkout", headers=new_token,
                        json={"cart_id": cart["id"], "cart_revision": cart["revision"]})
    assert (again.status_code, again.json()) == (403, {"detail": "Customer is inactive"})
    assert {s: m2_store_paths[s].read_bytes() for s in ("customers", "carts", "orders")} == {
        s: before[s] for s in ("customers", "carts", "orders")}


# --- #84: the role and ownership matrix on every customer endpoint ---------------------------

@pytest.mark.parametrize(("method", "path", "body"), CUSTOMER_ENDPOINTS)
def test_anonymous_callers_get_401_on_every_customer_endpoint(client, m2_store_paths, auth_accounts,
                                                              method, path, body):
    before = _bytes(m2_store_paths)
    for headers in ({}, {"Authorization": "Bearer not-a-real-token"},
                    {"Authorization": f"Bearer {auth_accounts.expired_token}"}):
        response = _call(client, method, path, body, headers)
        assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
        assert response.headers["www-authenticate"] == "Bearer"
    assert _bytes(m2_store_paths) == before


@pytest.mark.parametrize("role", ["restaurant_user", "administrator"])
@pytest.mark.parametrize(("method", "path", "body"), CUSTOMER_ENDPOINTS)
def test_staff_get_403_on_every_customer_endpoint(client, m2_store_paths, auth_accounts,
                                                  method, path, body, role):
    before = _bytes(m2_store_paths)
    response = _call(client, method, path, body, auth_accounts.headers(role))
    assert (response.status_code, response.json()) == (403, {"detail": "Operation not permitted"})
    assert _bytes(m2_store_paths) == before


def test_one_customer_can_never_reach_anothers_cart_or_orders(client, m2_store_paths, auth_accounts):
    ada = auth_accounts.headers("customer_a")
    ben = auth_accounts.headers("customer_b")
    order, cart = _buy_once_then_refill(client, ada)
    before = _bytes(m2_store_paths)

    # Ben has no cart and sees no orders; Ada's IDs do not help him.
    assert client.get("/customers/me/cart", headers=ben).status_code == 404
    assert client.get("/customers/me/orders", headers=ben).json() == []
    foreign = client.get(f"/customers/me/orders/{order['id']}", headers=ben)
    missing = client.get("/customers/me/orders/no-such-order", headers=ben)
    assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json()) == (
        404, {"detail": "Order not found"})
    stolen = client.post("/customers/me/checkout", headers=ben,
                         json={"cart_id": cart["id"], "cart_revision": cart["revision"]})
    assert (stolen.status_code, stolen.json()) == (404, {"detail": "Cart not found"})
    for method, path, body in [("PATCH", ITEM, {"quantity": 5}), ("DELETE", ITEM, None),
                               ("DELETE", "/customers/me/cart/items", None)]:
        assert _call(client, method, path, body, ben).status_code == 404, path
    assert _bytes(m2_store_paths) == before

    # Ben's own cart is separate: creating and filling it leaves Ada's cart and order as they were.
    assert client.put("/customers/me/cart", headers=ben).status_code == 201
    assert client.post("/customers/me/cart/items", headers=ben, json=ADD).status_code == 200
    adas_cart = client.get("/customers/me/cart", headers=ada).json()
    assert (adas_cart["id"], adas_cart["items"]) == (cart["id"], cart["items"])
    assert client.get(f"/customers/me/orders/{order['id']}", headers=ada).json() == order
