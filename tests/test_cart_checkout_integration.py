"""Carry a Food4Thought cart through checkout with real cart and order repositories.
A quantity accumulated past Python's 4300-digit integer-text limit must be purchased,
reloaded exactly from a fresh order store, and replayed to the same order (PR #113).
"""

from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.schemas.cart import AddCartItemRequest
from app.schemas.order import CheckoutRequest
from app.services.cart import CartService
from app.services.catalog import RestaurantCatalog
from app.services.checkout import CheckoutService
from contracts.m2 import Customer, FakeCustomers

ADA = Customer(id="customer-001", name="Ada Example", email="ada@example.invalid",
               delivery_address="101 Example Street", status="active")


def _checkout_service():
    return CheckoutService(lambda _principal: ADA, carts=CartRepository(),
                           catalog=RestaurantCatalog(), orders=OrderRepository())


def test_quantity_beyond_the_int_text_limit_survives_checkout_reload_and_retry(m2_store_paths):
    carts = CartService(carts=CartRepository(), customers=FakeCustomers([ADA]),
                        catalog=RestaurantCatalog(), receipts=OrderRepository())
    carts.create_or_get_cart("customer-001")
    add = dict(restaurant_id="restaurant-001", item_id="item-001")
    carts.add_item("customer-001", AddCartItemRequest(**add, quantity=10**4300 - 1))
    cart = carts.add_item("customer-001", AddCartItemRequest(**add, quantity=1))
    request = CheckoutRequest(cart_id=cart.id, cart_revision=cart.revision)

    first = _checkout_service().checkout("principal", request)

    assert first.created is True
    saved = OrderRepository().get_order(first.response.order.id)
    assert saved is not None and saved.items[0].quantity == 10**4300
    assert CartRepository().get_cart("customer-001").items == []
    retry = _checkout_service().checkout("principal", request)
    assert (retry.created, retry.response.order.id) == (False, first.response.order.id)
