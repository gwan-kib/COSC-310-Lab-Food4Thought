"""Validated checkout inputs and historical order snapshots for Food4Thought.
Money is stored in canonical decimal strings and checked with integer cents.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

from app.core.pricing import Money, cents, line_total, sum_line_totals

Identifier = Annotated[str, StringConstraints(min_length=1)]
Revision = Annotated[int, Field(ge=0)]


class OrderModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class CheckoutRequest(OrderModel):
    cart_id: Identifier
    cart_revision: Revision


class PurchasedItem(OrderModel):
    item_id: Identifier
    name: Identifier
    quantity: Annotated[int, Field(gt=0)]
    unit_price: Money
    line_total: Money

    @model_validator(mode="after")
    def verify_amounts(self) -> Self:
        if cents(self.unit_price) > 99900:
            raise ValueError("Unit price exceeds 999.00")
        if self.line_total != line_total(self.unit_price, self.quantity):
            raise ValueError("Line total does not match price and quantity")
        return self


class Order(OrderModel):
    id: Identifier
    customer_id: Identifier
    restaurant_id: Identifier
    restaurant_name: Identifier
    source_cart_id: Identifier
    source_cart_revision: Revision
    delivery_address: Identifier
    status: Literal["placed"]
    items: Annotated[
        tuple[PurchasedItem, ...],
        BeforeValidator(lambda items: tuple(items) if isinstance(items, list) else items),
        Field(min_length=1),
    ]
    subtotal: Money
    total: Money

    @model_validator(mode="after")
    def verify_purchase(self) -> Self:
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("Purchased item IDs must be unique within the restaurant")
        if self.subtotal != sum_line_totals(item.line_total for item in self.items):
            raise ValueError("Subtotal does not match the purchased items")
        if self.total != self.subtotal:
            raise ValueError("Total must equal subtotal")
        return self


class CheckoutResponse(OrderModel):
    order: Order
    cart_reset_pending: bool
