from uuid import uuid4

from app.repositories.restaurant import RestaurantRepository
from app.schemas.restaurant import Restaurant, RestaurantCreate, RestaurantRecord


class RestaurantService:
    """Provide restaurant discovery through the repository boundary."""

    def __init__(self, repository: RestaurantRepository) -> None:
        self.repository = repository

    def list_restaurants(self) -> list[Restaurant]:
        return self.repository.list_restaurants()

    def create_restaurant(self, request: RestaurantCreate) -> Restaurant:
        def add(records: list[RestaurantRecord]) -> Restaurant:
            existing_ids = {record.id for record in records}
            identifier = str(uuid4())
            while identifier in existing_ids:
                identifier = str(uuid4())

            record = RestaurantRecord(
                id=identifier, **request.model_dump(), menu_items=[]
            )
            records.append(record)
            return record.as_restaurant()

        return self.repository.mutate_records(add)
