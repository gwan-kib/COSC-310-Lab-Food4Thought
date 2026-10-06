from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema


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


class RestaurantUpdate(BaseModel):
    """Supply at least one mutable field; omission preserves its stored value."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1})

    # None represents omission internally, but is not valid request input.
    # Factories avoid documenting a null default in the non-nullable schema.
    name: WriteText | SkipJsonSchema[None] = Field(default_factory=lambda: None)
    cuisine: WriteText | SkipJsonSchema[None] = Field(default_factory=lambda: None)
    description: WriteText | SkipJsonSchema[None] = Field(default_factory=lambda: None)

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one restaurant field must be supplied")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Supplied restaurant fields cannot be null")
        return self


class MenuItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: WriteText
    description: WriteText
    price: str = Field(strict=True, pattern=r"^[0-9]+(\.[0-9]{1,2})?$")

    @field_validator("price")
    @classmethod
    def normalize_price(cls, value: str) -> str:
        return format(Decimal(value), ".2f")


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
