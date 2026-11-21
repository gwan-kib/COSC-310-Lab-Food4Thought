"""Carry a Food4Thought cart through checkout with real cart and order repositories.
A quantity accumulated past Python's 4300-digit integer-text limit must be purchased,
reloaded exactly from a fresh order store, and replayed to the same order (PR #113), and
every order line must be priced from one menu state (PR #115).
"""

from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.schemas.cart import AddCartItemRequest
from app.schemas.order import CheckoutRequest
from app.services.cart import CartService
from app.services.catalog import RestaurantCatalog
from app.services.checkout import CheckoutService
from contracts.m2 import CartItem, CartRecord, CatalogItem, Customer, FakeCartAccess, FakeCustomers

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


class ChangingMenuCatalog:
    """Each read returns the menu after one more concurrent price update, like a live store."""

    def __init__(self):
        self.menu_reads = 0
        self.restaurant = RestaurantCatalog().get_restaurant("restaurant-001")

    def _menu_now(self):
        self.menu_reads += 1
        bump = self.menu_reads  # item-002 always costs exactly 10.00 more than item-001
        return {"item-001": CatalogItem(id="item-001", name="Bowl", description="d",
                                        price=f"{10 + bump}.00", available=True),
                "item-002": CatalogItem(id="item-002", name="Udon", description="d",
                                        price=f"{20 + bump}.00", available=True)}

    def get_restaurant(self, restaurant_id):
        return self.restaurant if restaurant_id == "restaurant-001" else None

    def get_item(self, restaurant_id, item_id):
        return self._menu_now().get(item_id) if restaurant_id == "restaurant-001" else None

    def get_menu(self, restaurant_id):
        return self._menu_now() if restaurant_id == "restaurant-001" else None


def test_checkout_prices_every_order_line_from_one_menu_state(m2_store_paths):
    cart = CartRecord(id="cart-1", customer_id="customer-001", restaurant_id="restaurant-001",
                      revision=3, items=[CartItem(item_id="item-001", quantity=1),
                                         CartItem(item_id="item-002", quantity=1)])
    catalog = ChangingMenuCatalog()
    service = CheckoutService(lambda _principal: ADA, carts=FakeCartAccess([cart]),
                              catalog=catalog, orders=OrderRepository())

    order = service.checkout("principal", CheckoutRequest(cart_id="cart-1", cart_revision=3)).response.order

    assert catalog.menu_reads == 1
    prices = {line.item_id: line.unit_price for line in order.items}
    assert (prices["item-001"], prices["item-002"]) == ("11.00", "21.00")
    assert order.total == "32.00"
    assert OrderRepository().get_order(order.id).total == "32.00"
