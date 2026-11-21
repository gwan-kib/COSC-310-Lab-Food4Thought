"""Define Food4Thought's stored cart record, add-item request and priced cart view.
Carts store only item IDs and quantities; the view adds current names, prices and
totals that the cart service calculates from backend menu data.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(min_length=1)]
Money = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{2}$")]
# Strict, so 1.5, true and "2" are rejected instead of being coerced to an integer.
Quantity = Annotated[int, Field(strict=True, gt=0)]
Revision = Annotated[int, Field(strict=True, ge=0)]


class CartModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CartItem(CartModel):
    item_id: Identifier
    quantity: Quantity


class CartRecord(CartModel):
    """One customer's active cart as stored in carts.json."""

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
            raise ValueError("Each item has one cart line")
        return self


class AddCartItemRequest(CartModel):
    """Body of POST /customers/me/cart/items; prices and owner come from the backend."""

    restaurant_id: Identifier
    item_id: Identifier
    quantity: Quantity


class CartViewItem(CartModel):
    item_id: Identifier
    name: Identifier
    quantity: Quantity
    unit_price: Money
    line_total: Money
    available: bool


class CartView(CartModel):
    """A cart priced with current menu data; totals are recalculated on every read."""

    id: Identifier
    customer_id: Identifier
    revision: Revision
    restaurant_id: Identifier | None
    items: list[CartViewItem]
    subtotal: Money
    total: Money
    checkout_order_id: Identifier | None
