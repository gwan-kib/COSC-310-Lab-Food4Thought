"""Turn one owned cart revision into a durable Food4Thought order.
The saved snapshot is the receipt used to recover a failed or interrupted reset.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from app.core.storage import StorageFailure
from app.core.workflow import workflow_lock
from app.repositories.order import OrderRepository
from app.repositories.restaurant import RestaurantDataError
from app.schemas.order import CheckoutRequest, CheckoutResponse, Money, Order, PurchasedItem, cents, money
from app.schemas.restaurant import Restaurant


# Read-only views of the fields checkout consumes from other owners' stores.
class Customer(Protocol):
    id: str
    delivery_address: str


class CartLine(Protocol):
    item_id: str
    quantity: int


class Cart(Protocol):
    id: str
    customer_id: str
    revision: int
    restaurant_id: str | None

    @property
    def items(self) -> Sequence[CartLine]: ...


class CartAccess(Protocol):
    def get_cart(self, customer_id: str) -> Cart | None: ...
    def reset_after_order(self, customer_id: str, cart_id: str, expected_revision: int) -> bool: ...


class CatalogItem(Protocol):
    id: str
    name: str
    price: str
    available: bool


class CatalogAccess(Protocol):
    def get_restaurant(self, restaurant_id: str) -> Restaurant | None: ...
    # Every item of one restaurant from a single read, so all lines share one menu state.
    def get_menu(self, restaurant_id: str) -> Mapping[str, CatalogItem] | None: ...


class CartNotFound(Exception):
    """No cart or receipt owned by this customer matches the supplied ID."""


class CheckoutConflict(Exception):
    """Current cart or menu state prevents a new purchase."""


class CheckoutDataError(StorageFailure):
    """A participating store could not supply or persist consistent data."""

    def __init__(self) -> None:
        super().__init__("Checkout data is unavailable")


@dataclass(frozen=True)
class CheckoutResult:
    """The route can select 201 or 200 while keeping the same public body."""

    created: bool
    response: CheckoutResponse


_price = TypeAdapter(Money)


class CheckoutService[Principal]:
    def __init__(self, require_active_customer: Callable[[Principal], Customer],
                 carts: CartAccess, catalog: CatalogAccess, orders: OrderRepository) -> None:
        # Bind #84's require_customer to its store and active=True at composition time.
        self.require_active_customer = require_active_customer
        self.carts = carts
        self.catalog = catalog
        self.orders = orders

    def checkout(self, principal: Principal, request: CheckoutRequest) -> CheckoutResult:
        with workflow_lock:
            try:
                customer = self.require_active_customer(principal)
            except StorageFailure as exc:
                raise CheckoutDataError() from exc
            try:
                order = self.orders.find_for_cart(request.cart_id, request.cart_revision)
                created = order is None
                if order is None or order.customer_id != customer.id:
                    # Read the same private cart store for a foreign and an unknown
                    # attempt, even when that store is temporarily unavailable.
                    cart = self.carts.get_cart(customer.id)
                    if (
                        order is not None or cart is None
                        or cart.customer_id != customer.id or cart.id != request.cart_id
                    ):
                        raise CartNotFound("Cart not found")
                    order = self._new_order(customer, cart, request)
                    self.orders.save_order(order)
                pending = self._reset_purchased_cart(order)
            except CheckoutDataError:
                raise
            except (OSError, StorageFailure, RestaurantDataError, ValidationError) as exc:
                raise CheckoutDataError() from exc
            return CheckoutResult(created, CheckoutResponse(order=order, cart_reset_pending=pending))

    def _new_order(self, customer: Customer, cart: Cart, request: CheckoutRequest) -> Order:
        if cart.revision != request.cart_revision:
            raise CheckoutConflict("Cart revision changed")
        if bool(cart.items) != (cart.restaurant_id is not None):
            raise CheckoutDataError()
        if cart.restaurant_id is None:
            raise CheckoutConflict("Cart is empty")

        restaurant = self.catalog.get_restaurant(cart.restaurant_id)
        if restaurant is None or restaurant.id != cart.restaurant_id:
            raise CheckoutDataError()
        # One menu read prices every line, so a concurrent menu update cannot mix states.
        menu = self.catalog.get_menu(restaurant.id)
        if menu is None:
            raise CheckoutDataError()
        items = [self._purchase_line(menu, line) for line in cart.items]
        total = money(sum(cents(item.line_total) for item in items))
        order_id = str(uuid4())
        while self.orders.get_order(order_id) is not None:
            order_id = str(uuid4())
        return Order(
            id=order_id, customer_id=customer.id, restaurant_id=restaurant.id,
            restaurant_name=restaurant.name, source_cart_id=cart.id,
            source_cart_revision=cart.revision, delivery_address=customer.delivery_address,
            status="placed", items=items, subtotal=total, total=total,
        )

    def _purchase_line(self, menu: Mapping[str, CatalogItem], line: CartLine) -> PurchasedItem:
        item = menu.get(line.item_id)
        if item is None or item.id != line.item_id:
            raise CheckoutDataError()
        if type(line.quantity) is not int or line.quantity <= 0 or type(item.available) is not bool:
            raise CheckoutDataError()
        if not item.available:
            raise CheckoutConflict("Menu item is unavailable")
        price = _price.validate_python(item.price, strict=True)
        return PurchasedItem(item_id=item.id, name=item.name, quantity=line.quantity,
                             unit_price=price, line_total=money(cents(price) * line.quantity))

    def _reset_purchased_cart(self, order: Order) -> bool:
        """A conditional mismatch is safe. An uncertain write needs a fresh read."""
        try:
            self.carts.reset_after_order(order.customer_id, order.source_cart_id,
                                        order.source_cart_revision)
            return False
        except (StorageFailure, OSError, ValidationError):
            try:
                cart = self.carts.get_cart(order.customer_id)
            except (StorageFailure, OSError, ValidationError):
                return True
            return (cart is not None and cart.id == order.source_cart_id
                    and cart.revision == order.source_cart_revision)
