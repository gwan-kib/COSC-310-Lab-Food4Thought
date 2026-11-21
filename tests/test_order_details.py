"""Verify Food4Thought order detail ownership and historical snapshots across layers.
Use real authentication and disposable JSON stores, independently of checkout and
through a real checkout-service integration (the checkout HTTP route is pending).
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_principal, get_now
from app.main import app
from app.repositories.cart import CartRepository
from app.repositories.customer import CustomerDataError, CustomerRepository, SessionRepository
from app.repositories.order import OrderDataError, OrderRepository
from app.schemas.customer import Principal
from app.schemas.order import CheckoutRequest, Order
from app.services.auth import AuthService, AuthenticationRequiredError
from app.services.catalog import RestaurantCatalog
from app.services.checkout import CheckoutService
from app.services.customer import CustomerService
from contracts.auth import FIXED_NOW

URL = "/customers/me/orders/"
OWNER = Principal(account_id="customer-001", role="customer")


@pytest.fixture
def client(auth_accounts):
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_now, None)


@pytest.fixture
def saved_order(auth_accounts):
    source = Path(__file__).resolve().parents[1] / "docs/examples/m2.json"
    record = json.loads(source.read_text(encoding="utf-8"))["checkout_response"]["order"]
    OrderRepository().save_order(Order.model_validate(record))
    return record


def stores(paths):
    return {name: path.read_bytes() if path.is_file() else None for name, path in paths.items()}


def details_service():
    from app.services.order_details import OrderDetailsService
    return OrderDetailsService(CustomerRepository(), OrderRepository())


def test_owner_reads_complete_saved_order_without_writes(client, auth_accounts, saved_order):
    before = stores(auth_accounts.paths)
    response = client.get(URL + saved_order["id"], headers=auth_accounts.headers("customer_a"))
    assert response.status_code == 200
    assert response.json() == saved_order
    assert response.json()["total"] == "39.00"
    assert stores(auth_accounts.paths) == before


@pytest.mark.parametrize("account", ["customer_a", "customer_b"])
def test_missing_and_foreign_orders_have_identical_responses(client, auth_accounts, saved_order, account):
    # Give each caller another customer's existing ID and a nonexistent ID.
    record = saved_order | {"customer_id": "customer-002" if account == "customer_a" else "customer-001"}
    auth_accounts.paths["orders"].write_text(json.dumps([record]), encoding="utf-8")
    before = stores(auth_accounts.paths)
    foreign = client.get(URL + record["id"], headers=auth_accounts.headers(account))
    missing = client.get(URL + "missing", headers=auth_accounts.headers(account))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.content == missing.content == b'{"detail":"Order not found"}'
    assert stores(auth_accounts.paths) == before


@pytest.mark.parametrize("authorization", [None, "Basic abc", "Bearer", "Bearer unknown", "expired"])
def test_invalid_identity_is_denied_before_private_order_storage(client, auth_accounts, authorization):
    auth_accounts.paths["orders"].write_text("{broken", encoding="utf-8")
    if authorization == "expired":
        authorization = "Bearer " + auth_accounts.expired_token
    headers = {} if authorization is None else {"Authorization": authorization}
    before = stores(auth_accounts.paths)
    response = client.get(URL + "order-001", headers=headers)
    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
    assert response.headers["www-authenticate"] == "Bearer"
    assert stores(auth_accounts.paths) == before


@pytest.mark.parametrize("account", ["restaurant_user", "administrator"])
def test_staff_is_denied_before_private_order_storage(client, auth_accounts, account):
    auth_accounts.paths["orders"].write_text("{broken", encoding="utf-8")
    before = stores(auth_accounts.paths)
    response = client.get(URL + "order-001", headers=auth_accounts.headers(account))
    assert (response.status_code, response.json()) == (403, {"detail": "Operation not permitted"})
    assert stores(auth_accounts.paths) == before


def test_deactivated_owner_can_still_read_order_with_old_token(client, auth_accounts, saved_order):
    headers = auth_accounts.headers("customer_a")
    assert client.post("/customers/me/deactivate", headers=headers).status_code == 200
    before = stores(auth_accounts.paths)
    response = client.get(URL + saved_order["id"], headers=headers)
    assert response.status_code == 200 and response.json() == saved_order
    assert stores(auth_accounts.paths) == before


@pytest.mark.parametrize("damage", ["missing", "malformed", "invalid-total", "unreadable"])
@pytest.mark.parametrize("order_id", ["order-001", "missing"])
def test_order_storage_failure_is_generic_500_not_absence(client, auth_accounts, saved_order,
                                                        monkeypatch, damage, order_id):
    path = auth_accounts.paths["orders"]
    if damage == "missing":
        path.unlink()
    elif damage == "malformed":
        path.write_text("{private invalid data", encoding="utf-8")
    elif damage == "invalid-total":
        path.write_text(json.dumps([saved_order | {"total": "0.00"}]), encoding="utf-8")
    before = stores(auth_accounts.paths)
    with monkeypatch.context() as patch:
        if damage == "unreadable":
            read_bytes = Path.read_bytes
            def fail_order_read(candidate):
                if candidate == path:
                    raise PermissionError("private path and exception details")
                return read_bytes(candidate)
            patch.setattr(Path, "read_bytes", fail_order_read)
        response = client.get(URL + order_id, headers=auth_accounts.headers("customer_a"))
    assert (response.status_code, response.json()) == (500, {"detail": "Order data is unavailable"})
    assert stores(auth_accounts.paths) == before


@pytest.mark.parametrize("store", ["sessions", "customers"])
def test_authentication_store_failure_is_not_a_401(client, auth_accounts, saved_order, store):
    auth_accounts.paths[store].write_text("{broken", encoding="utf-8")
    before = stores(auth_accounts.paths)
    response = client.get(URL + saved_order["id"], headers=auth_accounts.headers("customer_a"))
    assert (response.status_code, response.json()) == (500, {"detail": "Authentication data is unavailable"})
    assert stores(auth_accounts.paths) == before


def test_service_rechecks_role_and_customer_before_order_lookup(auth_accounts, saved_order):
    from app.services.order_details import OrderAccessDeniedError
    auth_accounts.paths["orders"].write_text("{broken", encoding="utf-8")
    with pytest.raises(OrderAccessDeniedError):
        details_service().get_order(Principal(account_id="customer-001", role="administrator"), "order-001")
    with pytest.raises(AuthenticationRequiredError):
        details_service().get_order(Principal(account_id="missing", role="customer"), "order-001")


def test_service_ownership_and_reload_without_live_catalog_or_cart(auth_accounts, saved_order):
    from app.services.order_details import OrderNotFoundError
    auth_accounts.paths["restaurants"].write_text("{broken", encoding="utf-8")
    auth_accounts.paths["carts"].write_text("{broken", encoding="utf-8")
    first = details_service().get_order(OWNER, saved_order["id"])
    assert first.model_dump(mode="json") == saved_order
    assert details_service().get_order(OWNER, saved_order["id"]) == first
    other = Principal(account_id="customer-002", role="customer")
    for order_id in (saved_order["id"], "missing"):
        with pytest.raises(OrderNotFoundError, match="Order not found"):
            details_service().get_order(other, order_id)


def test_service_allows_inactive_but_rejects_removed_customer_on_reuse(auth_accounts, saved_order):
    service = details_service()
    CustomerService(CustomerRepository()).deactivate(OWNER.account_id)
    assert service.get_order(OWNER, saved_order["id"]).id == saved_order["id"]
    auth_accounts.paths["customers"].write_text("[]", encoding="utf-8")
    with pytest.raises(AuthenticationRequiredError):
        service.get_order(OWNER, saved_order["id"])


@pytest.mark.parametrize(("store", "error"), [("orders", OrderDataError), ("customers", CustomerDataError)])
def test_service_preserves_storage_failure_boundaries(auth_accounts, saved_order, store, error):
    auth_accounts.paths[store].write_text("{broken", encoding="utf-8")
    with pytest.raises(error):
        details_service().get_order(OWNER, saved_order["id"])


@pytest.mark.parametrize(("customer_data", "status", "detail"), [
    ("[]", 401, "Authentication required"), ("{broken", 500, "Customer data is unavailable"),
])
def test_customer_disappearing_or_failing_after_authentication_is_rechecked(
        client, auth_accounts, saved_order, customer_data, status, detail):
    def authenticated_before_change():
        auth_accounts.paths["customers"].write_text(customer_data, encoding="utf-8")
        return OWNER
    app.dependency_overrides[get_current_principal] = authenticated_before_change
    orders_before = auth_accounts.paths["orders"].read_bytes()
    try:
        response = client.get(URL + saved_order["id"])
    finally:
        app.dependency_overrides.pop(get_current_principal, None)
    assert (response.status_code, response.json()) == (status, {"detail": detail})
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    assert auth_accounts.paths["orders"].read_bytes() == orders_before


def test_detail_serializes_the_full_persisted_quantity_range(client, auth_accounts, saved_order):
    # Cart accumulation can exceed Python's integer-to-text limit (#113 regression).
    quantity = 10**4300
    amount = "125" + "0" * 4299 + ".00"
    item = saved_order["items"][0] | {"quantity": quantity, "line_total": amount}
    record = saved_order | {"id": "large-order", "source_cart_id": "large-cart",
                            "items": [item], "subtotal": amount, "total": amount}
    OrderRepository().save_order(Order.model_validate(record))
    response = client.get(URL + "large-order", headers=auth_accounts.headers("customer_a"))
    assert response.status_code == 200
    decoded = json.loads(response.content, parse_int=lambda text: int(Decimal(text)))
    assert decoded["items"][0]["quantity"] == quantity and decoded["total"] == amount


def test_openapi_documents_order_schema_security_and_errors(client):
    operation = client.get("/openapi.json").json()["paths"][URL + "{order_id}"]["get"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert set(operation["responses"]) == {"200", "401", "403", "404", "500"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Order"}


def test_real_account_cart_checkout_and_detail_preserve_history_after_reload(client, auth_accounts):
    # Real registration/login and HTTP cart; real checkout service until #91 exposes its route.
    registration = {"name": "New Customer", "email": "new@example.invalid",
                    "delivery_address": "10 Original Street", "password": "dummy-test-password"}
    customer = client.post("/customers", json=registration)
    assert customer.status_code == 201
    login = client.post("/auth/login", json={key: registration[key] for key in ("email", "password")})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    principal = AuthService(CustomerRepository(), SessionRepository()).resolve(token, FIXED_NOW)
    assert client.put("/customers/me/cart", headers=headers).status_code == 201
    cart_response = client.post("/customers/me/cart/items", headers=headers,
                               json={"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 2})
    assert cart_response.status_code == 200
    cart = cart_response.json()
    checkout = CheckoutService(CustomerService(CustomerRepository()).active_customer_for,
                               CartRepository(), RestaurantCatalog(), OrderRepository())
    purchased = checkout.checkout(principal, CheckoutRequest(cart_id=cart["id"], cart_revision=cart["revision"]))
    order_id = purchased.response.order.id
    assert purchased.created and CartRepository().get_cart(principal.account_id).items == []
    assert client.patch("/customers/me", headers=headers,
                        json={"delivery_address": "99 New Street"}).status_code == 200
    manager = auth_accounts.accounts["restaurant_user"]
    manager_login = client.post("/auth/login", json={
        "email": manager.record.email, "password": manager.password,
    })
    assert manager_login.status_code == 200
    manager_headers = {"Authorization": "Bearer " + manager_login.json()["access_token"]}
    assert client.patch("/restaurants/restaurant-001/menu/items/item-001",
                        headers=manager_headers,
                        json={"name": "Changed dish", "price": "99.00"}).status_code == 200
    assert client.patch("/restaurants/restaurant-001", headers=manager_headers,
                        json={"name": "Renamed restaurant"}).status_code == 200
    before = stores(auth_accounts.paths)
    with TestClient(app) as restarted_client:
        response = restarted_client.get(URL + order_id, headers=headers)
    assert response.status_code == 200
    order = response.json()
    assert order == purchased.response.order.model_dump(mode="json")
    assert (order["customer_id"], order["restaurant_id"], order["source_cart_id"], order["source_cart_revision"]) == (
        customer.json()["id"], "restaurant-001", cart["id"], cart["revision"])
    assert order["delivery_address"] == "10 Original Street"
    assert order["items"][0]["unit_price"] == "12.50" and order["total"] == "25.00"
    assert OrderRepository().get_order(order_id).model_dump(mode="json") == order
    assert stores(auth_accounts.paths) == before
