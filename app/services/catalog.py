"""Give carts and checkout a read-only view of Food4Thought's current restaurant menus.
Items are looked up under their own restaurant, so an item ID from another restaurant
is never found; availability defaults to true for menu items stored before it existed.
"""

from dataclasses import dataclass

from app.repositories.restaurant import RestaurantRepository
from app.schemas.restaurant import Restaurant


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    description: str
    price: str
    available: bool


class RestaurantCatalog:
    """Adapter from the restaurant repository to the M2 CatalogAccess interface."""

    def __init__(self, repository: RestaurantRepository | None = None) -> None:
        self.repository = repository or RestaurantRepository()

    def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        record = self.repository.get_record(restaurant_id)
        return None if record is None else record.as_restaurant()

    def get_item(self, restaurant_id: str, item_id: str) -> CatalogItem | None:
        record = self.repository.get_record(restaurant_id)
        if record is None:
            return None
        for item in record.menu_items:
            if item.id == item_id:
                return CatalogItem(id=item.id, name=item.name, description=item.description,
                                   price=item.price,
                                   # Menu availability (#94) adds this field; legacy items are orderable.
                                   available=getattr(item, "available", True))
        return None
