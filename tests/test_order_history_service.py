"""Verify Food4Thought history using independently persisted order snapshots.
Exercise the real history/checkout services and order repository; authorization,
customer, cart and catalog doubles do not establish real HTTP integration.
"""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from contracts.auth import Principal
from contracts.m2 import CartRecord, CatalogItem, Customer, FakeCartAccess, FakeCatalog
from app.core.storage import StorageFailure
from app.core.workflow import workflow_lock
from app.repositories.order import OrderDataError, OrderRepository
from app.schemas.order import CheckoutRequest
from app.schemas.restaurant import Restaurant
from app.services.checkout import CheckoutService


@pytest.fixture
def history_case(m2_store_paths):
    example_path = Path(__file__).resolve().parents[1] / "docs/examples/m2.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))["checkout_response"]["order"]
    # A1, B1, A2: lexical order differs from persistence order on purpose.
    records = []
    for order_id, owner, revision in [
        ("z-A1", "customer-a", 1), ("B1", "customer-b", 1), ("a-A2", "customer-a", 2),
    ]:
        record = deepcopy(example)
        record.update(id=order_id, customer_id=owner, source_cart_id=f"cart-{owner}",
                      source_cart_revision=revision)
        records.append(record)
    m2_store_paths["orders"].write_text(json.dumps(records), encoding="utf-8")
    customers = {
        owner: Customer(id=owner, name=owner, email=f"{owner}@example.invalid",
                        delivery_address="Current address", status="active")
        for owner in ["customer-a", "customer-b", "customer-empty"]
    }
    cart = CartRecord(id="cart-customer-a", customer_id="customer-a", revision=3,
                      restaurant_id="restaurant-001", items=[{"item_id": "item-001", "quantity": 1}])
    m2_store_paths["carts"].write_text(json.dumps([cart.model_dump()]), encoding="utf-8")

    def require_customer(principal):
        # Temporary #84 boundary: this assertion checks the service's lock scope.
        assert workflow_lock.locked()
        return customers[principal.account_id]

    return SimpleNamespace(paths=m2_store_paths, records=records, customers=customers,
                           require_customer=require_customer,
                           principal=Principal(account_id="customer-a", role="customer"))


def make_history(case, require_customer=None):
    # Keep the first red run a test failure on the absent application service.
    from app.services.order_history import OrderHistoryService

    return OrderHistoryService(require_customer or case.require_customer,
                               OrderRepository(case.paths["orders"]))


def stored_bytes(case):
    return {name: path.read_bytes() for name, path in case.paths.items() if path.exists()}


@pytest.mark.parametrize("owner,expected_ids", [
    ("customer-a", ["z-A1", "a-A2"]), ("customer-b", ["B1"]), ("customer-empty", []),
])
def test_history_filters_by_trusted_customer_without_reordering_or_writes(history_case, owner, expected_ids):
    before = stored_bytes(history_case)
    principal = Principal(account_id=owner, role="customer")
    result = make_history(history_case).list_orders(principal)
    assert [order.id for order in result] == expected_ids
    assert all(order.customer_id == owner for order in result)
    assert stored_bytes(history_case) == before


def test_fresh_history_preserves_snapshots_for_an_inactive_customer(history_case):
    history_case.customers["customer-a"].status = "inactive"
    history_case.customers["customer-a"].delivery_address = "Changed after purchase"
    before = stored_bytes(history_case)
    expected = [history_case.records[0], history_case.records[2]]
    for _ in range(2):
        result = make_history(history_case).list_orders(history_case.principal)
        assert [order.model_dump(mode="json") for order in result] == expected
        result.clear()
    assert stored_bytes(history_case) == before


@pytest.mark.parametrize("reason", ["Authentication required", "Operation not permitted"])
def test_authorization_denial_precedes_private_order_reads(history_case, reason):
    class AccessDenied(Exception):
        pass

    denial = AccessDenied(reason)
    principal = object()

    def deny(received):
        assert received is principal
        assert workflow_lock.locked()
        raise denial

    # If the service reads orders before checking access, corruption wins instead.
    history_case.paths["orders"].write_text("{", encoding="utf-8")
    before = stored_bytes(history_case)
    with pytest.raises(AccessDenied) as caught:
        make_history(history_case, deny).list_orders(principal)
    assert caught.value is denial
    assert stored_bytes(history_case) == before
    assert not workflow_lock.locked()


def test_customer_storage_failure_is_not_replaced_by_empty_history(history_case):
    failure = StorageFailure("Customer data is unavailable")

    def unavailable(principal):
        assert principal is history_case.principal
        assert workflow_lock.locked()
        raise failure

    before = stored_bytes(history_case)
    with pytest.raises(StorageFailure) as caught:
        make_history(history_case, unavailable).list_orders(history_case.principal)
    assert caught.value is failure
    assert stored_bytes(history_case) == before
    assert not workflow_lock.locked()


@pytest.mark.parametrize("damage", ["missing", "malformed", "invalid-foreign", "duplicate-id", "duplicate-attempt"])
@pytest.mark.parametrize("owner", ["customer-a", "customer-empty"])
def test_invalid_store_is_an_error_even_without_matching_orders(history_case, damage, owner):
    path = history_case.paths["orders"]
    records = history_case.records
    if damage == "missing":
        path.unlink()
    elif damage == "malformed":
        path.write_text("{", encoding="utf-8")
    else:
        if damage == "invalid-foreign":
            records[1]["total"] = "0.00"
        elif damage == "duplicate-id":
            records[1]["id"] = records[0]["id"]
        else:
            records[2]["source_cart_revision"] = records[0]["source_cart_revision"]
        path.write_text(json.dumps(records), encoding="utf-8")
    before = stored_bytes(history_case)
    with pytest.raises(OrderDataError, match="^Order data is unavailable$"):
        make_history(history_case).list_orders(Principal(account_id=owner, role="customer"))
    assert stored_bytes(history_case) == before
    assert not workflow_lock.locked()


def test_unreadable_store_is_an_error_without_changing_files(history_case, monkeypatch):
    path = history_case.paths["orders"]
    before = stored_bytes(history_case)
    original = Path.read_bytes

    def unreadable(candidate):
        if candidate == path:
            raise PermissionError("private filesystem detail")
        return original(candidate)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", unreadable)
        with pytest.raises(OrderDataError, match="^Order data is unavailable$"):
            make_history(history_case).list_orders(history_case.principal)
    assert stored_bytes(history_case) == before


def test_next_history_read_includes_checkout_receipt_after_repository_reload(history_case):
    history = make_history(history_case)
    assert [order.id for order in history.list_orders(history_case.principal)] == ["z-A1", "a-A2"]
    carts = FakeCartAccess([CartRecord(
        id="cart-customer-a", customer_id="customer-a", revision=3,
        restaurant_id="cafe", items=[{"item_id": "soup", "quantity": 2}],
    )])
    catalog = FakeCatalog(
        [Restaurant(id="cafe", name="Corner Cafe", cuisine="Cafe", description="Lunch")],
        {("cafe", "soup"): CatalogItem(id="soup", name="Soup", description="Bean",
                                      price="11.50", available=True)},
    )
    checkout = CheckoutService(history_case.require_customer, carts, catalog,
                               OrderRepository(history_case.paths["orders"]))
    purchase = checkout.checkout(history_case.principal,
                                 CheckoutRequest(cart_id="cart-customer-a", cart_revision=3))
    assert purchase.created and not purchase.response.cart_reset_pending
    saved = purchase.response.order
    assert (saved.total, saved.items[0].quantity) == ("23.00", 2)
    history_case.customers["customer-a"].delivery_address = "New address"
    catalog.items["cafe", "soup"].price = "50.00"
    before = stored_bytes(history_case)
    cart_after_checkout = carts.get_cart("customer-a")
    for service in [history, make_history(history_case)]:
        orders = service.list_orders(history_case.principal)
        assert [order.id for order in orders] == ["z-A1", "a-A2", saved.id]
        assert orders[-1] == saved
        assert orders[-1].delivery_address == "Current address"
    assert stored_bytes(history_case) == before
    assert carts.get_cart("customer-a") == cart_after_checkout
