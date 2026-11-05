"""Check Food4Thought's proposed M2 examples and reusable dependency doubles.
These checks validate the handoff contract, not unimplemented application routes.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.restaurant import Restaurant

from .m2 import (
    CartRecord, CartView, CatalogItem, CheckoutRequest, CheckoutResponse, Customer,
    FakeCartAccess, FakeCatalog, FakeCustomers, FakeOrders, Order, StorageFailure,
)


@pytest.fixture
def examples():
    path = Path(__file__).resolve().parents[2] / "docs/examples/m2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_examples_share_customer_cart_order_relationships_and_exact_money(examples):
    customer = Customer.model_validate(examples["customer"])
    cart = CartView.model_validate(examples["cart"])
    result = CheckoutResponse.model_validate(examples["checkout_response"])
    request = CheckoutRequest.model_validate(examples["checkout_request"])
    order = result.order
    assert customer.id == cart.customer_id == order.customer_id
    assert (request.cart_id, request.cart_revision) == (cart.id, cart.revision)
    assert (order.source_cart_id, order.source_cart_revision) == (cart.id, cart.revision)
    assert order.restaurant_id == cart.restaurant_id
    assert order.delivery_address == customer.delivery_address
    assert [item.model_dump() for item in order.items] == [
        item.model_dump(exclude={"available"}) for item in cart.items
    ]
    assert order.subtotal == order.total == cart.total == "39.00"
    assert [item.item_id for item in order.items] == [
        item["item_id"] for item in examples["cart_record"]["items"]
    ]


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "2"])
def test_cart_quantities_are_strict_positive_integers(examples, quantity):
    value = deepcopy(examples["cart_record"])
    value["items"][0]["quantity"] = quantity
    with pytest.raises(ValidationError):
        CartRecord.model_validate(value)


def test_cart_rejects_duplicate_item_lines_and_inconsistent_empty_state(examples):
    value = deepcopy(examples["cart_record"])
    value["items"].append(value["items"][0])
    with pytest.raises(ValidationError):
        CartRecord.model_validate(value)
    value["items"] = []
    with pytest.raises(ValidationError):
        CartRecord.model_validate(value)
    value["restaurant_id"] = None
    assert CartRecord.model_validate(value).items == []


@pytest.mark.parametrize("price", ["39", "39.0", 39.0, "NaN", "-1.00"])
def test_order_totals_are_canonical_decimal_strings(examples, price):
    value = deepcopy(examples["checkout_response"]["order"])
    value["total"] = price
    with pytest.raises(ValidationError):
        Order.model_validate(value)


def test_snapshot_rejects_arithmetic_and_scoped_identity_drift(examples):
    value = deepcopy(examples["checkout_response"]["order"])
    value["items"][0]["line_total"] = "0.00"
    with pytest.raises(ValidationError):
        Order.model_validate(value)
    value = deepcopy(examples["cart"])
    value["items"].append(value["items"][0])
    with pytest.raises(ValidationError):
        CartView.model_validate(value)


def test_customer_double_reflects_status_changes_without_aliasing(examples):
    customer = Customer.model_validate(examples["customer"])
    fake = FakeCustomers([customer])
    read = fake.get_customer(customer.id)
    read.name = "Changed outside the store"
    assert fake.get_customer(customer.id).name == customer.name
    fake.customers[customer.id].status = "inactive"
    assert fake.get_customer(customer.id).status == "inactive"
    assert fake.get_customer("missing") is None


def test_catalog_double_uses_restaurant_and_item_as_the_lookup_key(examples):
    item = CatalogItem.model_validate(examples["catalog_item"])
    other = item.model_copy(update={"price": "2.00"})
    restaurant = Restaurant.model_validate(examples["restaurant"])
    fake = FakeCatalog(
        [restaurant, restaurant.model_copy(update={"id": "restaurant-b"})],
        {(restaurant.id, item.id): item, ("restaurant-b", item.id): other},
    )
    assert fake.get_item("restaurant-b", item.id).price == "2.00"
    assert fake.get_item("missing", "shared-id") is None
    assert fake.get_restaurant(restaurant.id).name == "Cedar Bowl"
    assert fake.get_restaurant("missing") is None


def test_cart_view_can_show_an_unavailable_item_and_aggregate_above_unit_limit(examples):
    value = deepcopy(examples["cart"])
    value["items"][0].update(quantity=100, line_total="1250.00", available=False)
    value.update(subtotal="1264.00", total="1264.00")
    assert CartView.model_validate(value).total == "1264.00"


def test_empty_cart_and_shared_error_examples_are_usable(examples):
    empty = CartView.model_validate(examples["empty_cart"])
    assert (empty.items, empty.restaurant_id, empty.total) == ([], None, "0.00")
    for error in examples["errors"].values():
        assert error["status"] in {401, 403, 404, 409, 500}
        assert set(error["body"]) == {"detail"}
        assert isinstance(error["body"]["detail"], str)


def test_all_proposed_stores_have_explicit_disposable_paths(m2_store_paths, tmp_path):
    import os

    assert set(m2_store_paths) == {"restaurants", "customers", "carts", "orders"}
    for store in ("customers", "carts", "orders"):
        path = m2_store_paths[store]
        assert path.read_text(encoding="utf-8") == "[]\n"
        assert os.environ[f"{store.upper()}_DATA_PATH"] == str(path)
    assert all(path.parent == tmp_path for path in m2_store_paths.values())
    assert len(set(m2_store_paths.values())) == 4


def test_order_double_keeps_one_receipt_per_cart_revision(examples):
    order = Order.model_validate(examples["checkout_response"]["order"])
    fake = FakeOrders()
    assert fake.find_for_cart(order.source_cart_id, order.source_cart_revision) is None
    fake.save_order(order)
    assert fake.find_for_cart(order.source_cart_id, order.source_cart_revision) == order
    other = order.model_copy(update={"id": "another-order"})
    with pytest.raises(ValueError):
        fake.save_order(other)
    assert fake.list_for_customer(order.customer_id) == [order]
    assert fake.list_for_customer("someone-else") == []


def test_order_write_failure_does_not_change_double_state(examples):
    order = Order.model_validate(examples["checkout_response"]["order"])
    fake = FakeOrders(fail_save=True)
    with pytest.raises(StorageFailure):
        fake.save_order(order)
    assert fake.list_for_customer(order.customer_id) == []


def test_saved_order_survives_reset_failure_and_retry_reuses_receipt(examples):
    cart = CartRecord.model_validate(examples["cart_record"])
    order = Order.model_validate(examples["checkout_response"]["order"])
    carts = FakeCartAccess([cart], fail_reset=True)
    orders = FakeOrders()
    orders.save_order(order)
    with pytest.raises(StorageFailure):
        carts.reset_after_order(cart.customer_id, cart.id, cart.revision)
    assert carts.get_cart(cart.customer_id) == cart
    assert orders.find_for_cart(cart.id, cart.revision) == order
    carts.fail_reset = False
    carts.reset_after_order(cart.customer_id, cart.id, cart.revision)
    reset = carts.get_cart(cart.customer_id)
    assert (reset.id, reset.revision, reset.restaurant_id, reset.items) == (
        cart.id, cart.revision + 1, None, []
    )
    # A replay must not reset a later cart revision or somebody else's cart.
    assert carts.reset_after_order(cart.customer_id, cart.id, cart.revision) is False
    assert carts.reset_after_order("someone-else", cart.id, reset.revision) is False
    assert orders.list_for_customer(order.customer_id) == [order]
