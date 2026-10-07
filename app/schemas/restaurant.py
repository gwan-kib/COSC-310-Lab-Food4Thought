from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


WriteText = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)
]


class Restaurant(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)
    description: str = Field(min_length=1)


class RestaurantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: WriteText
    cuisine: WriteText
    description: WriteText


class MenuItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: WriteText
    description: WriteText
    price: str = Field(strict=True, pattern=r"^[0-9]+(\.[0-9]{1,2})?$")

    @field_validator("price")
    @classmethod
    def normalize_price(cls, value: str) -> str:
        return format(Decimal(value), ".2f")


class MenuItem(MenuItemCreate):
    id: str = Field(min_length=1)


class RestaurantRecord(BaseModel):
    """Complete stored record; legacy records may omit their empty menu."""

    # Existing M0 reads ignored extra fields; retain them across new writes.
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)
    description: str = Field(min_length=1)
    menu_items: list[MenuItem] = Field(default_factory=list)

    def as_restaurant(self) -> Restaurant:
        return Restaurant.model_validate(self.model_dump(exclude={"menu_items"}))


class Menu(BaseModel):
    """Read projection of one restaurant's single menu; not stored separately."""

    restaurant_id: str
    items: list[MenuItem]


class ErrorResponse(BaseModel):
    detail: str
