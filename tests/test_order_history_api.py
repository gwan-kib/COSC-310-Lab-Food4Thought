"""Exercise Food4Thought history through real bearer auth and isolated JSON stores.
Independent order fixtures cover read behavior; the integration flow creates a
purchase with the real checkout service before retrieving it through HTTP.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import get_auth_service, get_now
from app.core.workflow import workflow_lock
from app.main import app
from app.repositories.cart import CartRepository
from app.repositories.customer import CustomerDataError, CustomerRepository
from app.repositories.order import OrderRepository
from app.schemas.customer import Principal
from app.schemas.order import CheckoutRequest
from app.services.auth import AuthenticationRequiredError
from app.services.catalog import RestaurantCatalog
from app.services.checkout import CheckoutService
from app.services.customer import CustomerService
from contracts.auth import FIXED_NOW

HISTORY = "/customers/me/orders"


@pytest.fixture
def client(m2_store_paths):
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_now, None)


@pytest.fixture
def independent_orders(m2_store_paths, auth_accounts):
    example = json.loads((Path(__file__).resolve().parents[1] / "docs/examples/m2.json")
                         .read_text(encoding="utf-8"))["checkout_response"]["order"]
    orders = []
    for order_id, customer, revision in [
        ("z-A1", "customer-001", 1), ("B1", "customer-002", 1), ("a-A2", "customer-001", 2),
    ]:
        order = deepcopy(example)
        order.update(id=order_id, customer_id=customer, source_cart_id=f"cart-{customer}",
                     source_cart_revision=revision)
        orders.append(order)
    m2_store_paths["orders"].write_text(json.dumps(orders), encoding="utf-8")
    return orders


def store_bytes(paths):
    return {name: path.read_bytes() if path.exists() else None for name, path in paths.items()}


def register_and_login(client, email="new@example.invalid"):
    response = client.post("/customers", json={"name": "New Customer", "email": email,
                           "password": "test-password-92", "delivery_address": "92 Example Lane"})
    assert response.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": "test-password-92"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return response.json(), token, {"Authorization": f"Bearer {token}"}


def test_history_is_scoped_ordered_and_read_only(client, m2_store_paths, auth_accounts, independent_orders):
    # A spoofed query does not replace the trusted bearer identity.
    before = store_bytes(m2_store_paths)
    ada = client.get(HISTORY + "?customer_id=customer-002", headers=auth_accounts.headers("customer_a"))
    ben = client.get(HISTORY, headers=auth_accounts.headers("customer_b"))
    assert (ada.status_code, ada.json()) == (200, [independent_orders[0], independent_orders[2]])
    assert (ben.status_code, ben.json()) == (200, [independent_orders[1]])
    assert store_bytes(m2_store_paths) == before


def test_customer_without_orders_gets_an_empty_array(client, m2_store_paths, independent_orders):
    _, _, headers = register_and_login(client)
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=headers)
    assert (response.status_code, response.json()) == (200, [])
    assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("authorization", [None, "", "Basic abc", "Bearer", "Bearer unknown", "expired"])
def test_invalid_identity_is_401_before_order_reads(client, m2_store_paths, auth_accounts, authorization):
    if authorization == "expired":
        authorization = f"Bearer {auth_accounts.expired_token}"
    m2_store_paths["orders"].write_text("{", encoding="utf-8")
    headers = {} if authorization is None else {"Authorization": authorization}
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=headers)
    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
    assert response.headers["www-authenticate"] == "Bearer"
    assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("role", ["restaurant_user", "administrator"])
def test_staff_cannot_read_history(client, m2_store_paths, auth_accounts, role):
    m2_store_paths["orders"].write_text("{", encoding="utf-8")
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=auth_accounts.headers(role))
    assert (response.status_code, response.json()) == (403, {"detail": "Operation not permitted"})
    assert store_bytes(m2_store_paths) == before


def test_deleted_customer_identity_is_401(client, m2_store_paths, auth_accounts, independent_orders):
    customers = json.loads(m2_store_paths["customers"].read_text(encoding="utf-8"))
    m2_store_paths["customers"].write_text(json.dumps(customers[1:]), encoding="utf-8")
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=auth_accounts.headers("customer_a"))
    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
    assert response.headers["www-authenticate"] == "Bearer"
    assert store_bytes(m2_store_paths) == before


def test_inactive_customer_can_read_with_old_and_new_tokens(client, m2_store_paths, auth_accounts, independent_orders):
    old_headers = auth_accounts.headers("customer_a")
    assert client.post("/customers/me/deactivate", headers=old_headers).status_code == 200
    login = client.post("/auth/login", json={"email": "ada@example.invalid",
                        "password": auth_accounts.accounts["customer_a"].password})
    assert login.status_code == 200
    before = store_bytes(m2_store_paths)
    for headers in [old_headers, {"Authorization": f"Bearer {login.json()['access_token']}"}]:
        response = client.get(HISTORY, headers=headers)
        assert (response.status_code, response.json()) == (200, [independent_orders[0], independent_orders[2]])
    assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("damage", ["missing", "malformed", "invalid-foreign", "duplicate"])
def test_bad_order_store_is_500_even_for_empty_history(client, m2_store_paths, independent_orders, damage):
    _, _, headers = register_and_login(client)
    path = m2_store_paths["orders"]
    if damage == "missing":
        path.unlink()
    elif damage == "malformed":
        path.write_text("{", encoding="utf-8")
    else:
        if damage == "invalid-foreign":
            independent_orders[1]["total"] = "0.00"
        else:
            independent_orders.append(independent_orders[0])
        path.write_text(json.dumps(independent_orders), encoding="utf-8")
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=headers)
    assert (response.status_code, response.json()) == (500, {"detail": "Order data is unavailable"})
    assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("store", ["customers", "sessions"])
def test_corrupt_identity_store_is_not_401(client, m2_store_paths, auth_accounts, store):
    m2_store_paths[store].write_text("{", encoding="utf-8")
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=auth_accounts.headers("customer_a"))
    assert (response.status_code, response.json()) == (500, {"detail": "Authentication data is unavailable"})
    assert store_bytes(m2_store_paths) == before


@pytest.mark.parametrize("failure,status,detail", [
    ("missing", 401, "Authentication required"), ("storage", 500, "Customer data is unavailable"),
])
def test_service_rechecks_customer_after_token_resolution(client, m2_store_paths, auth_accounts,
                                                        monkeypatch, failure, status, detail):
    original = CustomerRepository.get_customer
    reads = 0

    def changed_after_auth(repository, customer_id):
        nonlocal reads
        reads += 1
        if reads == 1:
            return original(repository, customer_id)
        assert workflow_lock.locked()
        if failure == "storage":
            raise CustomerDataError("private path and record details")
        return None

    monkeypatch.setattr(CustomerRepository, "get_customer", changed_after_auth)
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=auth_accounts.headers("customer_a"))
    assert (response.status_code, response.json()) == (status, {"detail": detail})
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert reads == 2
    assert store_bytes(m2_store_paths) == before


def test_real_service_rejects_noncustomer_even_without_http_precheck(m2_store_paths, auth_accounts):
    from app.api.routes.order_history import get_order_history_service
    from app.services.order_history import OrderHistoryNotPermittedError

    # Role denial must precede any private customer/order read in the service too.
    m2_store_paths["customers"].write_text("{", encoding="utf-8")
    before = store_bytes(m2_store_paths)
    with pytest.raises(OrderHistoryNotPermittedError):
        get_order_history_service().list_orders(Principal(account_id="customer-001", role="administrator"))
    assert store_bytes(m2_store_paths) == before


def test_real_service_rejects_missing_customer(m2_store_paths):
    from app.api.routes.order_history import get_order_history_service

    with pytest.raises(AuthenticationRequiredError):
        get_order_history_service().list_orders(Principal(account_id="missing", role="customer"))


def test_real_purchase_survives_profile_menu_changes_and_fresh_history_app(client, m2_store_paths):
    customer, token, headers = register_and_login(client)
    assert client.put("/customers/me/cart", headers=headers).status_code == 201
    added = client.post("/customers/me/cart/items", headers=headers, json={
        "restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2})
    assert added.status_code == 200
    cart = added.json()
    principal = get_auth_service().resolve(token, FIXED_NOW)
    checkout = CheckoutService(CustomerService(CustomerRepository()).active_customer_for,
                               CartRepository(), RestaurantCatalog(), OrderRepository())
    purchase = checkout.checkout(principal, CheckoutRequest(cart_id=cart["id"], cart_revision=cart["revision"]))
    order = purchase.response.order
    assert purchase.created and not purchase.response.cart_reset_pending
    assert order.customer_id == customer["id"] and order.total == "25.00"
    assert CartRepository().get_cart(customer["id"]).items == []
    assert client.patch("/customers/me", headers=headers, json={"delivery_address": "New address"}).status_code == 200
    # Simulate a later catalog change without depending on menu-management auth.
    restaurants = json.loads(m2_store_paths["restaurants"].read_text(encoding="utf-8"))
    restaurants[0]["menu_items"][0]["price"] = "99.00"
    m2_store_paths["restaurants"].write_text(json.dumps(restaurants), encoding="utf-8")
    before = store_bytes(m2_store_paths)
    response = client.get(HISTORY, headers=headers)
    assert (response.status_code, response.json()) == (200, [order.model_dump(mode="json")])

    from app.api.routes.order_history import router

    fresh_app = FastAPI()
    fresh_app.include_router(router)
    fresh_app.dependency_overrides[get_now] = lambda: FIXED_NOW
    with TestClient(fresh_app) as fresh_client:
        reloaded = fresh_client.get(HISTORY, headers=headers)
    assert (reloaded.status_code, reloaded.json()) == (200, response.json())
    assert OrderRepository().get_order(order.id) == order
    assert store_bytes(m2_store_paths) == before


def test_history_openapi_documents_bearer_array_and_errors(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][HISTORY]["get"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    responses = operation["responses"]
    assert set(responses) == {"200", "401", "403", "500"}
    body = responses["200"]["content"]["application/json"]["schema"]
    assert body["type"] == "array" and body["items"] == {"$ref": "#/components/schemas/Order"}
    for code in ["401", "403", "500"]:
        assert responses[code]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
