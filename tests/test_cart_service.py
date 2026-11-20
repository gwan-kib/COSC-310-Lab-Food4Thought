"""Check Food4Thought's cart service rules for creating carts (#85) and adding items (#86).
Customers and order receipts use the M2 contract fakes; menu data comes from the real
restaurant repository on an isolated copy, so prices and parents are the backend's.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.storage import StorageFailure
from app.repositories.cart import CartDataError, CartRepository
from app.schemas.cart import AddCartItemRequest, CartItem, CartRecord
from app.schemas.order import cents, money
from app.services.cart import (
    CartNotFoundError, CartRestaurantConflictError, CartService,
    CheckoutRecoveryRequiredError, CustomerInactiveError, CustomerNotFoundError,
    MenuItemUnavailableError,
)
from app.services.catalog import RestaurantCatalog
from app.services.restaurant import MenuItemNotFoundError, RestaurantNotFoundError
from contracts.m2 import CatalogItem, Customer, FakeCatalog, FakeCustomers

ADA = Customer(id="customer-001", name="Ada Example", email="ada@example.invalid",
               delivery_address="101 Example Street", status="active")
INACTIVE = ADA.model_copy(update={"id": "customer-009", "status": "inactive"})


class Receipts:
    """Order-receipt lookup double: optionally reports a saved order for one revision."""

    def __init__(self, pending=None, owner="customer-001"):
        self.pending = pending
        self.owner = owner

    def find_for_cart(self, cart_id, revision):
        if self.pending == (cart_id, revision):
            return SimpleNamespace(id="order-123", customer_id=self.owner)
        return None


def _service(catalog=None, receipts=None):
    return CartService(
        carts=CartRepository(), customers=FakeCustomers([ADA, INACTIVE]),
        catalog=catalog or RestaurantCatalog(), receipts=receipts or Receipts(),
    )


def _add(restaurant_id="restaurant-001", item_id="item-001", quantity=2):
    return AddCartItemRequest(restaurant_id=restaurant_id, item_id=item_id, quantity=quantity)


# --- #85: create or retrieve the active cart ---------------------------------------

def test_active_customer_creates_then_retrieves_the_same_empty_cart(m2_store_paths):
    service = _service()
    view, created = service.create_or_get_cart("customer-001")
    again, created_again = service.create_or_get_cart("customer-001")

    assert created is True and created_again is False
    assert again.id == view.id
    assert (view.revision, view.restaurant_id, view.items) == (0, None, [])
    assert (view.subtotal, view.total, view.checkout_order_id) == ("0.00", "0.00", None)


def test_inactive_or_unknown_customer_cannot_create_a_cart(m2_store_paths):
    with pytest.raises(CustomerInactiveError):
        _service().create_or_get_cart("customer-009")
    with pytest.raises(CustomerNotFoundError):
        _service().create_or_get_cart("customer-404")
    assert json.loads(m2_store_paths["carts"].read_text()) == []


def test_get_cart_never_creates_one_and_inactive_customers_can_still_read(m2_store_paths):
    with pytest.raises(CartNotFoundError):
        _service().get_cart("customer-001")
    assert json.loads(m2_store_paths["carts"].read_text()) == []

    CartRepository().create_cart("customer-009")
    assert _service().get_cart("customer-009").items == []


# --- #86: add a menu item ---------------------------------------------------------

def test_add_item_binds_the_restaurant_and_prices_from_backend_menu_data(m2_store_paths):
    service = _service()
    cart, _ = service.create_or_get_cart("customer-001")

    view = service.add_item("customer-001", _add(quantity=2))

    assert (view.id, view.revision, view.restaurant_id) == (cart.id, 1, "restaurant-001")
    [line] = view.items
    assert (line.item_id, line.name, line.quantity) == ("item-001", "Vegetable bowl", 2)
    assert (line.unit_price, line.line_total, line.available) == ("12.50", "25.00", True)
    assert (view.subtotal, view.total) == ("25.00", "25.00")


def test_adding_the_same_item_again_increments_its_line(m2_store_paths):
    service = _service()
    service.create_or_get_cart("customer-001")
    service.add_item("customer-001", _add(quantity=2))
    view = service.add_item("customer-001", _add(quantity=1))
    view = service.add_item("customer-001", _add(item_id="item-002", quantity=1))

    assert [(line.item_id, line.quantity) for line in view.items] == [("item-001", 3), ("item-002", 1)]
    assert view.revision == 3
    assert (view.subtotal, view.total) == ("51.50", "51.50")


def test_contents_and_totals_reload_from_a_fresh_service(m2_store_paths):
    _service().create_or_get_cart("customer-001")
    added = _service().add_item("customer-001", _add(quantity=2))

    assert _service().get_cart("customer-001") == added


def test_item_from_another_restaurant_is_rejected_without_changes(m2_store_paths):
    service = _service()
    service.create_or_get_cart("customer-001")
    service.add_item("customer-001", _add())
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(CartRestaurantConflictError):
        service.add_item("customer-001", _add(restaurant_id="restaurant-002", item_id="item-003"))

    assert m2_store_paths["carts"].read_bytes() == before
    assert service.get_cart("customer-001").total == "25.00"


@pytest.mark.parametrize(("restaurant_id", "item_id", "error"), [
    ("restaurant-404", "item-001", RestaurantNotFoundError),
    ("restaurant-001", "item-404", MenuItemNotFoundError),
    ("restaurant-001", "item-003", MenuItemNotFoundError),  # item-003 belongs to restaurant-002
])
def test_missing_or_wrong_parent_items_are_rejected_without_writes(m2_store_paths, restaurant_id, item_id, error):
    service = _service()
    service.create_or_get_cart("customer-001")
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(error):
        service.add_item("customer-001", _add(restaurant_id=restaurant_id, item_id=item_id))

    assert m2_store_paths["carts"].read_bytes() == before


def test_unavailable_item_is_rejected_without_writes(m2_store_paths):
    restaurant = RestaurantCatalog().get_restaurant("restaurant-001")
    unavailable = CatalogItem(id="item-001", name="Vegetable bowl", description="Seasonal",
                              price="12.50", available=False)
    service = _service(catalog=FakeCatalog([restaurant], {("restaurant-001", "item-001"): unavailable}))
    service.create_or_get_cart("customer-001")
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(MenuItemUnavailableError):
        service.add_item("customer-001", _add())

    assert m2_store_paths["carts"].read_bytes() == before


def test_inactive_customer_cannot_add_and_nothing_is_written(m2_store_paths):
    CartRepository().create_cart("customer-009")
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(CustomerInactiveError):
        _service().add_item("customer-009", _add())

    assert m2_store_paths["carts"].read_bytes() == before


def test_adding_requires_an_existing_cart(m2_store_paths):
    with pytest.raises(CartNotFoundError):
        _service().add_item("customer-001", _add())
    assert json.loads(m2_store_paths["carts"].read_text()) == []


def test_cart_with_a_saved_order_awaiting_reset_cannot_be_edited(m2_store_paths):
    cart, _ = CartRepository().create_cart("customer-001")
    service = _service(receipts=Receipts(pending=(cart.id, 0)))
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(CheckoutRecoveryRequiredError):
        service.add_item("customer-001", _add())

    assert m2_store_paths["carts"].read_bytes() == before
    assert service.get_cart("customer-001").checkout_order_id == "order-123"


def test_failed_save_preserves_the_previous_cart(m2_store_paths, monkeypatch):
    service = _service()
    service.create_or_get_cart("customer-001")
    service.add_item("customer-001", _add(quantity=1))
    before = m2_store_paths["carts"].read_bytes()

    def broken_replace(*_args):
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.cart.os.replace", broken_replace)
    with pytest.raises(CartDataError):
        service.add_item("customer-001", _add(quantity=1))

    assert m2_store_paths["carts"].read_bytes() == before


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "2", None])
def test_invalid_quantities_are_rejected_by_the_request_model(quantity):
    with pytest.raises(ValidationError):
        AddCartItemRequest(restaurant_id="restaurant-001", item_id="item-001", quantity=quantity)


def test_client_cannot_supply_price_total_or_owner():
    for extra in ({"price": "0.01"}, {"total": "0.00"}, {"customer_id": "customer-002"}):
        with pytest.raises(ValidationError):
            AddCartItemRequest.model_validate(
                {"restaurant_id": "restaurant-001", "item_id": "item-001", "quantity": 1, **extra})


# --- PR #113 review regressions ---------------------------------------------------

def test_failed_view_read_after_add_leaves_the_cart_file_unchanged(m2_store_paths):
    # A stored line whose menu item has disappeared makes the priced view fail.
    cart, _ = CartRepository().create_cart("customer-001")
    CartRepository().save_cart(CartRecord(id=cart.id, customer_id="customer-001", revision=3,
                                          restaurant_id="restaurant-001",
                                          items=[CartItem(item_id="item-gone", quantity=1)]))
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(CartDataError):
        _service().add_item("customer-001", _add(quantity=1))

    assert m2_store_paths["carts"].read_bytes() == before


class FailingReceipts:
    def find_for_cart(self, cart_id, revision):
        raise StorageFailure("order store unavailable")


def test_failed_receipt_read_on_create_saves_no_cart(m2_store_paths):
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(StorageFailure):
        _service(receipts=FailingReceipts()).create_or_get_cart("customer-001")

    assert m2_store_paths["carts"].read_bytes() == before


@pytest.mark.parametrize(("restaurant_id", "item_id"), [
    ("restaurant-002", "item-404"),   # other restaurant, missing item
    ("restaurant-404", "item-001"),   # missing restaurant
])
def test_mixed_restaurant_is_reported_before_missing_restaurant_or_item(m2_store_paths, restaurant_id, item_id):
    service = _service()
    service.create_or_get_cart("customer-001")
    service.add_item("customer-001", _add())
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(CartRestaurantConflictError):
        service.add_item("customer-001", _add(restaurant_id=restaurant_id, item_id=item_id))

    assert m2_store_paths["carts"].read_bytes() == before


def test_totals_beyond_the_int_text_limit_match_checkout_money(m2_store_paths):
    # Same quantity as checkout's regression: the total has more than 4300 digits.
    quantity = 10**4299 + 1
    service = _service()
    service.create_or_get_cart("customer-001")

    view = service.add_item("customer-001", _add(quantity=quantity))

    expected = money(cents("12.50") * quantity)
    assert view.items[0].line_total == view.subtotal == view.total == expected
    assert _service().get_cart("customer-001") == view


def test_concurrent_creates_produce_one_cart(m2_store_paths):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _service().create_or_get_cart("customer-001"), range(8)))

    assert len({view.id for view, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    assert len(json.loads(m2_store_paths["carts"].read_text())) == 1


def test_receipt_owned_by_another_customer_exposes_no_order_id(m2_store_paths):
    cart, _ = CartRepository().create_cart("customer-001")
    service = _service(receipts=Receipts(pending=(cart.id, 0), owner="customer-002"))

    with pytest.raises(CartDataError):
        service.get_cart("customer-001")


def test_receipt_owned_by_another_customer_does_not_block_or_change_an_add(m2_store_paths):
    cart, _ = CartRepository().create_cart("customer-001")
    service = _service(receipts=Receipts(pending=(cart.id, 0), owner="customer-002"))
    before = m2_store_paths["carts"].read_bytes()

    with pytest.raises(CartDataError):
        service.add_item("customer-001", _add())

    assert m2_store_paths["carts"].read_bytes() == before


def test_repeated_add_across_the_int_text_limit_saves_and_reloads_exactly(m2_store_paths):
    service = _service()
    service.create_or_get_cart("customer-001")
    service.add_item("customer-001", _add(quantity=10**4300 - 1))  # 4300 digits

    view = service.add_item("customer-001", _add(quantity=1))      # now 4301 digits

    assert view.items[0].quantity == 10**4300
    assert CartRepository().get_cart("customer-001").items[0].quantity == 10**4300
    assert _service().get_cart("customer-001") == view
