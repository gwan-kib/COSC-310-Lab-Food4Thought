from app.repositories.restaurant import RestaurantRepository
from app.schemas.restaurant import Restaurant


class RestaurantService:
    """Provide restaurant discovery through the repository boundary."""

    def __init__(self, repository: RestaurantRepository) -> None:
        self.repository = repository

    def list_restaurants(self) -> list[Restaurant]:
        return self.repository.list_restaurants()
