"""Apply Food4Thought's cart rules: create or read a customer's active cart (#85) and
add menu items (#86). Edits run under the shared workflow lock, re-read the customer's
current status, and price lines from current menu data rather than client input.
"""

from typing import Protocol

from app.core.workflow import workflow_lock
from app.repositories.cart import CartDataError, CartRepository
from app.schemas.cart import AddCartItemRequest, CartItem, CartRecord, CartView, CartViewItem
from app.services.catalog import CatalogItem
from app.services.restaurant import MenuItemNotFoundError, RestaurantNotFoundError


class CustomerRecord(Protocol):
    id: str
    status: str


class CustomerAccess(Protocol):
    def get_customer(self, customer_id: str) -> CustomerRecord | None: ...


class CatalogAccess(Protocol):
    def get_restaurant(self, restaurant_id: str) -> object | None: ...
    def get_item(self, restaurant_id: str, item_id: str) -> CatalogItem | None: ...


class OrderReceipts(Protocol):
    """Read-only lookup of an order already saved for a cart revision (#91)."""

    def find_for_cart(self, cart_id: str, revision: int) -> object | None: ...


class CustomerNotFoundError(Exception):
    """The authenticated customer's record no longer exists."""


class CustomerInactiveError(Exception):
    """A deactivated customer cannot create or change a cart."""


class CartNotFoundError(Exception):
    """The customer has no active cart yet."""


class CartRestaurantConflictError(Exception):
    """The cart already holds items from a different restaurant."""


class MenuItemUnavailableError(Exception):
    """The menu item exists but cannot be ordered right now."""


class CheckoutRecoveryRequiredError(Exception):
    """An order was saved for this cart revision but the cart was not reset yet."""


def _cents(price: str) -> int:
    # Prices are validated "12.50" strings; integer cents avoid float rounding.
    whole, _, fraction = price.partition(".")
    return int(whole) * 100 + int(fraction.ljust(2, "0")[:2])


def _money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


class CartService:
    def __init__(self, carts: CartRepository, customers: CustomerAccess,
                 catalog: CatalogAccess, receipts: OrderReceipts) -> None:
        self.carts = carts
        self.customers = customers
        self.catalog = catalog
        self.receipts = receipts

    def create_or_get_cart(self, customer_id: str) -> tuple[CartView, bool]:
        """Return the active cart, creating an empty one on first use (PUT .../cart)."""
        with workflow_lock:
            self._require_active(customer_id)
            cart, created = self.carts.create_cart(customer_id)
            return self._view(cart), created

    def get_cart(self, customer_id: str) -> CartView:
        """Read the cart without creating it; inactive customers may still read."""
        with workflow_lock:
            cart = self.carts.get_cart(customer_id)
            if cart is None:
                raise CartNotFoundError(customer_id)
            return self._view(cart)

    def add_item(self, customer_id: str, request: AddCartItemRequest) -> CartView:
        """Add a quantity of one current, available menu item to the customer's cart."""
        with workflow_lock:
            self._require_active(customer_id)
            cart = self.carts.get_cart(customer_id)
            if cart is None:
                raise CartNotFoundError(customer_id)
            if self.receipts.find_for_cart(cart.id, cart.revision) is not None:
                raise CheckoutRecoveryRequiredError(cart.id)
            if self.catalog.get_restaurant(request.restaurant_id) is None:
                raise RestaurantNotFoundError(request.restaurant_id)
            item = self.catalog.get_item(request.restaurant_id, request.item_id)
            if item is None:
                raise MenuItemNotFoundError(request.item_id)
            if not item.available:
                raise MenuItemUnavailableError(request.item_id)
            if cart.restaurant_id not in (None, request.restaurant_id):
                raise CartRestaurantConflictError(cart.restaurant_id)

            items = [line.model_copy() for line in cart.items]
            existing = next((line for line in items if line.item_id == request.item_id), None)
            if existing is None:
                items.append(CartItem(item_id=request.item_id, quantity=request.quantity))
            else:
                existing.quantity += request.quantity
            updated = CartRecord(id=cart.id, customer_id=customer_id, revision=cart.revision + 1,
                                 restaurant_id=request.restaurant_id, items=items)
            self.carts.save_cart(updated)
            return self._view(updated)

    def _require_active(self, customer_id: str) -> None:
        customer = self.customers.get_customer(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        if customer.status != "active":
            raise CustomerInactiveError(customer_id)

    def _view(self, cart: CartRecord) -> CartView:
        lines = []
        for line in cart.items:
            item = self.catalog.get_item(cart.restaurant_id, line.item_id)
            if item is None:
                # A stored reference to a missing item is corrupt data, not a free item.
                raise CartDataError(f"Cart {cart.id} references missing item {line.item_id}")
            line_cents = _cents(item.price) * line.quantity
            lines.append(CartViewItem(item_id=item.id, name=item.name, quantity=line.quantity,
                                      unit_price=_money(_cents(item.price)),
                                      line_total=_money(line_cents), available=item.available))
        subtotal = _money(sum(_cents(line.line_total) for line in lines))
        receipt = self.receipts.find_for_cart(cart.id, cart.revision)
        return CartView(id=cart.id, customer_id=cart.customer_id, revision=cart.revision,
                        restaurant_id=cart.restaurant_id, items=lines, subtotal=subtotal,
                        total=subtotal, checkout_order_id=None if receipt is None else receipt.id)
