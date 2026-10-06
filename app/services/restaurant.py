from uuid import uuid4

from app.repositories.restaurant import RestaurantRepository
from app.schemas.restaurant import (
    Menu,
    Restaurant,
    RestaurantCreate,
    RestaurantRecord,
)


class RestaurantNotFoundError(Exception):
    """No restaurant exists with the requested identifier."""


class RestaurantService:
    """Provide restaurant discovery through the repository boundary."""

    def __init__(self, repository: RestaurantRepository) -> None:
        self.repository = repository

    def list_restaurants(self) -> list[Restaurant]:
        return self.repository.list_restaurants()

    def get_menu(self, restaurant_id: str) -> Menu:
        # The repository only reports absence; treating it as an error is an
        # application decision, so it is made here rather than in storage.
        record = self.repository.get_record(restaurant_id)
        if record is None:
            raise RestaurantNotFoundError(restaurant_id)
        return Menu(restaurant_id=record.id, items=record.menu_items)

    def create_restaurant(self, request: RestaurantCreate) -> Restaurant:
        def add(records: list[RestaurantRecord]) -> None:
            existing_ids = {record.id for record in records}
            identifier = str(uuid4())
            while identifier in existing_ids:
                identifier = str(uuid4())

            record = RestaurantRecord(
                id=identifier, **request.model_dump(), menu_items=[]
            )
            records.append(record)

        return self.repository.mutate_records(add)[-1].as_restaurant()
