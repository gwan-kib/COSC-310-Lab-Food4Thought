"""Exercise checkout against a real, isolated order store and M2 boundary doubles.
Verify the exact saved transaction and what survives failures, retries and restart.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from contracts.auth import Principal
from contracts.m2 import CartRecord, CatalogItem, Customer, FakeCartAccess, FakeCatalog
from app.core.workflow import workflow_lock
from app.repositories.order import OrderDataError, OrderRepository
from app.schemas.order import CheckoutRequest
from app.schemas.restaurant import Restaurant
from app.services.checkout import (
    CartNotFound, CheckoutConflict, CheckoutDataError, CheckoutService,
)


class Example:
    """A customer last saw Soup at 10.00; checkout must read the live catalog."""

    def __init__(self, path):
        self.path = path
        self.principal = Principal(account_id="buyer", role="customer")
        self.customer = Customer(id="buyer", name="Pat", email="p@example.invalid",
                                 delivery_address="Unit 4", status="active")
        self.request = CheckoutRequest(cart_id="cart", cart_revision=5)
        self.carts = FakeCartAccess([CartRecord(id="cart", customer_id="buyer", revision=5,
                                                restaurant_id="cafe", items=[{"item_id": "s", "quantity": 2}])])
        self.catalog = FakeCatalog(
            [Restaurant(id="cafe", name="Corner Cafe", cuisine="Cafe", description="Lunch")],
            {("cafe", "s"): CatalogItem(id="s", name="Soup", description="Bean",
                                         price="10.00", available=True)},
        )

    def active_customer(self, principal):
        # Stand-in for #84's require_customer(..., active=True) bound to customer storage.
        assert workflow_lock.locked()
        if principal.role != "customer" or self.customer.status != "active":
            raise PermissionError("Access denied")
        assert principal.account_id == self.customer.id
        return self.customer

    def checkout(self, request=None, orders=None):
        service = CheckoutService(self.active_customer, self.carts, self.catalog,
                                  orders or OrderRepository(self.path))
        return service.checkout(self.principal, request or self.request)


@pytest.fixture
def example(m2_store_paths):
    return Example(m2_store_paths["orders"])


def test_reprice_snapshot_save_and_clear_only_purchased_revision(example):
    example.catalog.items["cafe", "s"].price = "11.50"
    example.customer.delivery_address = "Unit 9"
    result = example.checkout()
    assert result.created and not result.response.cart_reset_pending
    order = result.response.order
    assert order.model_dump(mode="json", exclude={"id"}) == {
        "customer_id": "buyer", "restaurant_id": "cafe", "restaurant_name": "Corner Cafe",
        "source_cart_id": "cart", "source_cart_revision": 5, "delivery_address": "Unit 9",
        "status": "placed", "subtotal": "23.00", "total": "23.00",
        "items": [{"item_id": "s", "name": "Soup", "quantity": 2,
                   "unit_price": "11.50", "line_total": "23.00"}],
    }
    assert OrderRepository().get_order(order.id) == order
    cart = example.carts.carts["buyer"]
    assert (cart.id, cart.revision, cart.restaurant_id, cart.items) == ("cart", 6, None, [])
    example.catalog.items.clear()
    example.customer.delivery_address = "Unit 10"
    replay = example.checkout()
    assert not replay.created and replay.response == result.response


@pytest.mark.parametrize("new_cart", [False, True])
def test_reopen_after_failed_reset_recovers_once_without_erasing_later_cart(example, monkeypatch, new_cart):
    before = example.carts.get_cart("buyer")
    with monkeypatch.context() as patch:
        patch.setattr(example.carts, "fail_reset", True)
        first = example.checkout()
        assert first.created and first.response.cart_reset_pending
        assert example.carts.get_cart("buyer") == before
        assert OrderRepository().list_for_customer("buyer") == [first.response.order]
        again = example.checkout()
        assert not again.created and again.response == first.response
    if new_cart:
        example.carts.carts["buyer"].revision += 1
        example.carts.carts["buyer"].items[0].quantity = 3
    replay = example.checkout()
    assert not replay.created and not replay.response.cart_reset_pending
    assert replay.response.order == first.response.order
    assert OrderRepository().list_for_customer("buyer") == [first.response.order]
    current = example.carts.get_cart("buyer")
    assert current.revision == 6
    assert [line.quantity for line in current.items] == ([3] if new_cart else [])


@pytest.mark.parametrize("actually_saved", [False, True])
def test_failed_or_uncertain_save_keeps_cart_and_retry_checks_disk(example, monkeypatch, actually_saved):
    original = example.carts.get_cart("buyer")
    repo = OrderRepository()
    save = repo.save_order

    def fail(order):
        if actually_saved:
            save(order)
        raise OrderDataError("injected failure")

    monkeypatch.setattr(repo, "save_order", fail)
    with pytest.raises(CheckoutDataError, match="Checkout data is unavailable"):
        example.checkout(orders=repo)
    assert example.carts.get_cart("buyer") == original
    receipts = OrderRepository().list_for_customer("buyer")
    assert len(receipts) == int(actually_saved)
    result = example.checkout()
    assert result.created is not actually_saved
    assert OrderRepository().list_for_customer("buyer") == [result.response.order]
    if actually_saved:
        assert result.response.order == receipts[0]


@pytest.mark.parametrize("problem,error,detail", [
    ("no_cart", CartNotFound, "Cart not found"),
    ("other_id", CartNotFound, "Cart not found"),
    ("stale", CheckoutConflict, "Cart revision changed"),
    ("empty", CheckoutConflict, "Cart is empty"),
    ("unavailable", CheckoutConflict, "Menu item is unavailable"),
    ("missing_parent", CheckoutDataError, "Checkout data is unavailable"),
    ("missing_item", CheckoutDataError, "Checkout data is unavailable"),
    ("quantity", CheckoutDataError, "Checkout data is unavailable"),
])
def test_rejection_preserves_cart_and_orders(example, problem, error, detail):
    cart = example.carts.carts["buyer"]
    if problem == "no_cart":
        example.carts.carts.clear()
    elif problem == "other_id":
        example.request = CheckoutRequest(cart_id="other", cart_revision=5)
    elif problem == "stale":
        example.request = CheckoutRequest(cart_id="cart", cart_revision=4)
    elif problem == "empty":
        example.carts.carts["buyer"] = CartRecord(id="cart", customer_id="buyer", revision=5,
                                                  restaurant_id=None, items=[])
    elif problem == "unavailable":
        example.catalog.items["cafe", "s"].available = False
    elif problem == "missing_parent":
        example.catalog.restaurants.clear()
    elif problem == "missing_item":
        example.catalog.items.clear()
    else:
        cart.items[0] = cart.items[0].model_copy(update={"quantity": 0})
    before = example.carts.get_cart("buyer")
    with pytest.raises(error, match=detail):
        example.checkout()
    assert example.carts.get_cart("buyer") == before
    assert OrderRepository().list_for_customer("buyer") == []


@pytest.mark.parametrize("purchased", [False, True])
def test_foreign_live_cart_and_foreign_receipt_are_indistinguishable(example, purchased):
    if purchased:
        example.checkout()
    original = example.carts.get_cart("buyer")
    order_bytes = example.path.read_bytes()
    example.customer.id = "other"
    example.principal = Principal(account_id="other", role="customer")
    with pytest.raises(CartNotFound, match="^Cart not found$"):
        example.checkout()
    assert example.carts.get_cart("buyer") == original
    assert example.path.read_bytes() == order_bytes


@pytest.mark.parametrize("purchased", [False, True])
def test_deactivation_completed_under_workflow_lock_rejects_purchase_and_replay(example, purchased):
    if purchased:
        example.checkout()
    before = example.carts.get_cart("buyer")
    data = example.path.read_bytes()
    started = Event()

    def submit():
        started.set()
        return example.checkout()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with workflow_lock:
            future = pool.submit(submit)
            assert started.wait(5)
            example.customer.status = "inactive"
        with pytest.raises(PermissionError):
            future.result(timeout=5)
    assert example.path.read_bytes() == data
    assert example.carts.get_cart("buyer") == before


def test_two_callers_for_same_attempt_get_one_order(example):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: example.checkout(), range(2)))
    assert sorted(result.created for result in results) == [False, True]
    assert results[0].response == results[1].response
    assert OrderRepository().list_for_customer("buyer") == [results[0].response.order]
    assert example.carts.get_cart("buyer").revision == 6


def test_foreign_receipt_and_unknown_attempt_match_during_cart_store_outage(example, monkeypatch):
    first = example.checkout()
    example.customer.id = "other"
    example.principal = Principal(account_id="other", role="customer")

    def unavailable(*args):
        raise OSError("injected cart read failure")

    monkeypatch.setattr(example.carts, "get_cart", unavailable)
    for cart_id in ["cart", "unknown"]:
        with pytest.raises(CheckoutDataError):
            example.checkout(CheckoutRequest(cart_id=cart_id, cart_revision=5))
    assert OrderRepository().list_for_customer("buyer") == [first.response.order]


@pytest.mark.parametrize("readable", [False, True])
def test_reset_reports_failure_after_cart_was_cleared(example, monkeypatch, readable):
    from pydantic import ValidationError

    reset = example.carts.reset_after_order

    def cannot_read(*args):
        raise OSError("cart store unavailable")

    def uncertain_reset(*args):
        reset(*args)
        if not readable:
            monkeypatch.setattr(example.carts, "get_cart", cannot_read)
        raise ValidationError.from_exception_data("injected cart data failure", [])

    monkeypatch.setattr(example.carts, "reset_after_order", uncertain_reset)
    result = example.checkout()
    assert result.created and result.response.cart_reset_pending is (not readable)
    assert OrderRepository().get_order(result.response.order.id) == result.response.order
