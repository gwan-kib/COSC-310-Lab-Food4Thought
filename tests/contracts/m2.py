"""Provide Food4Thought's proposed M2 handoff models and in-memory test doubles.
Feature owners may reuse these examples and ports; no application route imports
this module, and the doubles do not implement checkout, authorization, or file I/O.
"""

from copy import deepcopy
from typing import Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.restaurant import Restaurant


Identifier = Annotated[str, StringConstraints(min_length=1)]
Money = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{2}$")]
Quantity = Annotated[int, Field(strict=True, gt=0)]
Revision = Annotated[int, Field(strict=True, ge=0)]


def cents(value: str) -> int:
    """Use integer cents so quantity multiplication never uses float rounding."""
    return int(value.replace(".", ""))


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


class Customer(ContractModel):
    id: Identifier
    name: Identifier
    email: Identifier
    delivery_address: Identifier
    status: Literal["active", "inactive"]


class CartItem(ContractModel):
    item_id: Identifier
    quantity: Quantity


class CartRecord(ContractModel):
    id: Identifier
    customer_id: Identifier
    revision: Revision
    restaurant_id: Identifier | None
    items: list[CartItem]

    @model_validator(mode="after")
    def consistent_scope(self) -> Self:
        if bool(self.items) != (self.restaurant_id is not None):
            raise ValueError("Only a nonempty cart has a restaurant")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("Each scoped item has one cart line")
        return self


class PurchasedItem(ContractModel):
    item_id: Identifier
    name: Identifier
    quantity: Quantity
    unit_price: Money
    line_total: Money

    @model_validator(mode="after")
    def exact_line_total(self) -> Self:
        if cents(self.unit_price) > 99900:
            raise ValueError("Preserve the adopted 999.00 unit-price limit")
        if cents(self.line_total) != cents(self.unit_price) * self.quantity:
            raise ValueError("Line total must match unit price times quantity")
        return self


class CatalogItem(ContractModel):
    id: Identifier
    name: Identifier
    description: Identifier
    price: Money
    available: bool

    @model_validator(mode="after")
    def existing_price_limit(self) -> Self:
        if cents(self.price) > 99900:
            raise ValueError("Preserve the adopted 999.00 unit-price limit")
        return self


class CartViewItem(PurchasedItem):
    available: bool


class Totals(ContractModel):
    subtotal: Money
    total: Money

    def check_totals(self, items: list[PurchasedItem]) -> None:
        if len({item.item_id for item in items}) != len(items):
            raise ValueError("Each scoped item has one transaction line")
        if cents(self.subtotal) != sum(cents(item.line_total) for item in items):
            raise ValueError("Subtotal must match the sum of line totals")
        if self.total != self.subtotal:
            raise ValueError("M2 adds no fees, taxes, discounts or payments")


class CartView(Totals):
    id: Identifier
    customer_id: Identifier
    revision: Revision
    restaurant_id: Identifier | None
    items: list[CartViewItem]
    checkout_order_id: Identifier | None

    @model_validator(mode="after")
    def consistent_view(self) -> Self:
        if bool(self.items) != (self.restaurant_id is not None):
            raise ValueError("Only a nonempty cart has a restaurant")
        self.check_totals(self.items)
        return self


class CheckoutRequest(ContractModel):
    cart_id: Identifier
    cart_revision: Revision


class Order(Totals):
    id: Identifier
    customer_id: Identifier
    restaurant_id: Identifier
    restaurant_name: Identifier
    source_cart_id: Identifier
    source_cart_revision: Revision
    delivery_address: Identifier
    status: Literal["placed"]
    items: Annotated[list[PurchasedItem], Field(min_length=1)]

    @model_validator(mode="after")
    def consistent_transaction(self) -> Self:
        self.check_totals(self.items)
        return self


class CheckoutResponse(ContractModel):
    order: Order
    cart_reset_pending: bool


class CustomerAccess(Protocol):
    def get_customer(self, customer_id: str) -> Customer | None: ...


class CatalogAccess(Protocol):
    def get_restaurant(self, restaurant_id: str) -> Restaurant | None: ...
    def get_item(self, restaurant_id: str, item_id: str) -> CatalogItem | None: ...


class CartAccess(Protocol):
    def get_cart(self, customer_id: str) -> CartRecord | None: ...
    def reset_after_order(
        self, customer_id: str, cart_id: str, expected_revision: int
    ) -> bool: ...


class OrderAccess(Protocol):
    def find_for_cart(self, cart_id: str, revision: int) -> Order | None: ...
    def save_order(self, order: Order) -> None: ...
    def get_order(self, order_id: str) -> Order | None: ...
    def list_for_customer(self, customer_id: str) -> list[Order]: ...


class StorageFailure(Exception):
    """Test-only injected storage failure; application owners map their errors."""


class FakeCustomers:
    def __init__(self, customers: list[Customer]):
        self.customers = {customer.id: customer.model_copy(deep=True) for customer in customers}
        if len(self.customers) != len(customers):
            raise ValueError("Customer IDs must be unique")

    def get_customer(self, customer_id: str) -> Customer | None:
        return deepcopy(self.customers.get(customer_id))


class FakeCatalog:
    """Expose already-resolved menu data without replacing restaurant business rules."""

    def __init__(
        self, restaurants: list[Restaurant], items: dict[tuple[str, str], CatalogItem]
    ):
        self.restaurants = {restaurant.id: restaurant.model_copy(deep=True)
                            for restaurant in restaurants}
        self.items = deepcopy(items)
        for (restaurant_id, item_id), item in self.items.items():
            if restaurant_id not in self.restaurants or item_id != item.id:
                raise ValueError("Catalog items need a valid scoped parent and ID")

    def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        return deepcopy(self.restaurants.get(restaurant_id))

    def get_item(self, restaurant_id: str, item_id: str) -> CatalogItem | None:
        return deepcopy(self.items.get((restaurant_id, item_id)))


class FakeCartAccess:
    def __init__(self, carts: list[CartRecord], *, fail_reset: bool = False):
        self.carts = {cart.customer_id: cart.model_copy(deep=True) for cart in carts}
        if len(self.carts) != len(carts):
            raise ValueError("Only one active cart per customer")
        if len({cart.id for cart in carts}) != len(carts):
            raise ValueError("Cart IDs must be unique")
        self.fail_reset = fail_reset

    def get_cart(self, customer_id: str) -> CartRecord | None:
        return deepcopy(self.carts.get(customer_id))

    def reset_after_order(
        self, customer_id: str, cart_id: str, expected_revision: int
    ) -> bool:
        cart = self.carts.get(customer_id)
        if cart is None or cart.id != cart_id or cart.revision != expected_revision:
            return False
        if self.fail_reset:
            raise StorageFailure("Injected cart reset failure")
        self.carts[customer_id] = CartRecord(
            id=cart.id, customer_id=customer_id, revision=cart.revision + 1,
            restaurant_id=None, items=[],
        )
        return True


class FakeOrders:
    def __init__(self, *, fail_save: bool = False):
        self.orders: dict[str, Order] = {}
        self.fail_save = fail_save

    def find_for_cart(self, cart_id: str, revision: int) -> Order | None:
        return next((order.model_copy(deep=True) for order in self.orders.values()
                     if (order.source_cart_id, order.source_cart_revision) == (cart_id, revision)), None)

    def save_order(self, order: Order) -> None:
        if self.fail_save:
            raise StorageFailure("Injected order save failure")
        if order.id in self.orders or self.find_for_cart(order.source_cart_id, order.source_cart_revision):
            raise ValueError("Order ID and source cart revision must both be unique")
        self.orders[order.id] = Order.model_validate(order.model_dump())

    def get_order(self, order_id: str) -> Order | None:
        return deepcopy(self.orders.get(order_id))

    def list_for_customer(self, customer_id: str) -> list[Order]:
        return [order.model_copy(deep=True) for order in self.orders.values()
                if order.customer_id == customer_id]
