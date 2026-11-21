"""Apply Food4Thought cart rules for creation, reads, item additions, quantity edits,
removal and clearing. Changes check current customer status under the shared workflow
lock and build backend-priced responses before saving.
"""

from typing import Protocol

from app.core.pricing import line_total, sum_line_totals
from app.core.workflow import workflow_lock
from app.repositories.cart import CartDataError, CartRepository
from app.schemas.cart import AddCartItemRequest, CartItem, CartRecord, CartView, CartViewItem
from app.schemas.cart import UpdateCartQuantityRequest
from app.services.catalog import CatalogItem
from app.services.restaurant import MenuItemNotFoundError, RestaurantNotFoundError


class CustomerRecord(Protocol):
    id: str
    status: str


class CustomerAccess(Protocol):
    def get_customer(self, customer_id: str) -> CustomerRecord | None: ...


class CatalogAccess(Protocol):
    def get_menu(self, restaurant_id: str) -> dict[str, CatalogItem] | None:
        """All items of one restaurant from a single read; None if the restaurant is missing."""


class OrderReceipts(Protocol):
    """Read-only lookup of an order already saved for a cart revision (#91)."""

    def find_for_cart(self, cart_id: str, revision: int) -> object | None: ...


class CustomerNotFoundError(Exception):
    """The authenticated customer's record no longer exists."""


class CustomerInactiveError(Exception):
    """A deactivated customer cannot create or change a cart."""


class CartNotFoundError(Exception):
    """The customer has no active cart yet."""


class CartItemNotFoundError(Exception):
    """The selected item is not a line in the customer's cart."""


class CartRestaurantConflictError(Exception):
    """The cart already holds items from a different restaurant."""


class MenuItemUnavailableError(Exception):
    """The menu item exists but cannot be ordered right now."""


class CheckoutRecoveryRequiredError(Exception):
    """An order was saved for this cart revision but the cart was not reset yet."""


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
            new_views: list[CartView] = []
            cart, created = self.carts.create_cart(
                customer_id, before_save=lambda new: new_views.append(self._view(new)))
            return (new_views[0] if created else self._view(cart)), created

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
            # Contract order: receipt, mixed restaurant, restaurant, item, availability.
            if self._receipt_for(cart) is not None:
                raise CheckoutRecoveryRequiredError(cart.id)
            if cart.restaurant_id not in (None, request.restaurant_id):
                raise CartRestaurantConflictError(cart.restaurant_id)
            # One menu snapshot validates the item and prices the whole response.
            menu = self.catalog.get_menu(request.restaurant_id)
            if menu is None:
                raise RestaurantNotFoundError(request.restaurant_id)
            item = menu.get(request.item_id)
            if item is None:
                raise MenuItemNotFoundError(request.item_id)
            if not item.available:
                raise MenuItemUnavailableError(request.item_id)

            items = [line.model_copy() for line in cart.items]
            existing = next((line for line in items if line.item_id == request.item_id), None)
            if existing is None:
                items.append(CartItem(item_id=request.item_id, quantity=request.quantity))
            else:
                existing.quantity += request.quantity
            updated = CartRecord(id=cart.id, customer_id=customer_id, revision=cart.revision + 1,
                                 restaurant_id=request.restaurant_id, items=items)
            view = self._view(updated, menu)  # every fallible read happens before the write
            self.carts.save_cart(updated)
            return view

    def update_quantity(self, customer_id: str, item_id: str, request: UpdateCartQuantityRequest) -> CartView:
        """Set one existing line and price the result before committing the edit."""
        with workflow_lock:
            self._require_active(customer_id)
            cart = self.carts.get_cart(customer_id)
            if cart is None:
                raise CartNotFoundError(customer_id)
            if self._receipt_for(cart) is not None:
                raise CheckoutRecoveryRequiredError(cart.id)
            line = next((line for line in cart.items if line.item_id == item_id), None)
            if line is None:
                raise CartItemNotFoundError(item_id)

            menu = self.catalog.get_menu(cart.restaurant_id)
            if menu is None or item_id not in menu:
                raise CartDataError(f"Cart {cart.id} references a missing restaurant or item")
            if not menu[item_id].available:
                raise MenuItemUnavailableError(item_id)
            if line.quantity == request.quantity:
                return self._view(cart, menu)

            line.quantity = request.quantity
            cart.revision += 1
            view = self._view(cart, menu)
            self.carts.save_cart(cart)
            return view

    def remove_item(self, customer_id: str, item_id: str) -> CartView:
        """Remove one owned line, including an unavailable item, and persist its priced result."""
        with workflow_lock:
            self._require_active(customer_id)
            cart = self.carts.get_cart(customer_id)
            if cart is None:
                raise CartNotFoundError(customer_id)
            if not any(line.item_id == item_id for line in cart.items):
                raise CartItemNotFoundError(item_id)
            if self._receipt_for(cart) is not None:
                raise CheckoutRecoveryRequiredError(cart.id)

            # Unavailable items can be removed; missing stored references are still corruption.
            menu = self.catalog.get_menu(cart.restaurant_id)
            if menu is None or item_id not in menu:
                raise CartDataError(f"Cart {cart.id} references a missing restaurant or item")
            items = [line.model_copy() for line in cart.items if line.item_id != item_id]
            updated = CartRecord(id=cart.id, customer_id=cart.customer_id, revision=cart.revision + 1,
                                 restaurant_id=cart.restaurant_id if items else None, items=items)
            view = self._view(updated, menu)  # validate remaining references before the write
            self.carts.save_cart(updated)
            return view

    def clear_cart(self, customer_id: str) -> CartView:
        """Empty an owned cart once; an already empty cart keeps its revision without a save."""
        with workflow_lock:
            self._require_active(customer_id)
            cart = self.carts.get_cart(customer_id)
            if cart is None:
                raise CartNotFoundError(customer_id)
            if self._receipt_for(cart) is not None:
                raise CheckoutRecoveryRequiredError(cart.id)

            # Unavailable items may be cleared, but invalid stored references stay errors.
            current = self._view(cart)
            if not cart.items:
                return current
            updated = CartRecord(id=cart.id, customer_id=cart.customer_id,
                                 revision=cart.revision + 1, restaurant_id=None, items=[])
            view = self._view(updated)
            if view.checkout_order_id is not None:
                # Mismatched backups must not reuse a revision already recorded in orders.
                raise CartDataError(f"Next revision of cart {cart.id} was already purchased")
            self.carts.save_cart(updated)
            return view

    def _require_active(self, customer_id: str) -> None:
        customer = self.customers.get_customer(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        if customer.status != "active":
            raise CustomerInactiveError(customer_id)

    def _receipt_for(self, cart: CartRecord) -> object | None:
        """The saved order for this cart revision, checked to belong to the cart's customer."""
        receipt = self.receipts.find_for_cart(cart.id, cart.revision)
        if receipt is not None and getattr(receipt, "customer_id", None) != cart.customer_id:
            # Never reveal another customer's order or let it block this customer's cart.
            raise CartDataError(f"Order receipt for cart {cart.id} belongs to another customer")
        return receipt

    def _view(self, cart: CartRecord, menu: dict[str, CatalogItem] | None = None) -> CartView:
        if cart.items and menu is None:
            menu = self.catalog.get_menu(cart.restaurant_id)
            if menu is None:
                raise CartDataError(f"Cart {cart.id} references missing restaurant {cart.restaurant_id}")
        lines = []
        for line in cart.items:
            item = menu.get(line.item_id)
            if item is None:
                # A stored reference to a missing item is corrupt data, not a free item.
                raise CartDataError(f"Cart {cart.id} references missing item {line.item_id}")
            lines.append(CartViewItem(item_id=item.id, name=item.name, quantity=line.quantity,
                                      unit_price=item.price,
                                      line_total=line_total(item.price, line.quantity),
                                      available=item.available))
        subtotal = sum_line_totals(line.line_total for line in lines)
        receipt = self._receipt_for(cart)
        return CartView(id=cart.id, customer_id=cart.customer_id, revision=cart.revision,
                        restaurant_id=cart.restaurant_id, items=lines, subtotal=subtotal,
                        total=subtotal, checkout_order_id=None if receipt is None else receipt.id)
