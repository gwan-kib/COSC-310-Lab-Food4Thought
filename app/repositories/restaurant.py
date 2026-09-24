import json
from pathlib import Path

from pydantic import ValidationError

from app.core.config import get_restaurants_data_path
from app.schemas.restaurant import Restaurant


class RestaurantDataError(Exception):
    """Restaurant data could not be read or validated."""


class RestaurantRepository:
    """Load restaurant records from the configured JSON file."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_restaurants_data_path()

    def list_restaurants(self) -> list[Restaurant]:
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RestaurantDataError(
                f"Could not read restaurant data from {self.path}: {exc}"
            ) from exc

        if not isinstance(records, list):
            raise RestaurantDataError(
                f"Restaurant data in {self.path} must be a JSON array"
            )

        try:
            return [Restaurant.model_validate(record) for record in records]
        except ValidationError as exc:
            raise RestaurantDataError(
                f"Invalid restaurant record in {self.path}: {exc}"
            ) from exc
