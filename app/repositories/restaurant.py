import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Callable

from pydantic import ValidationError

from app.core.config import get_restaurants_data_path
from app.schemas.restaurant import Restaurant, RestaurantRecord


_mutation_lock = Lock()


class RestaurantDataError(Exception):
    """Restaurant data could not be read or validated."""


class RestaurantRepository:
    """Load and atomically replace complete restaurant records in one process."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_restaurants_data_path()

    def list_restaurants(self) -> list[Restaurant]:
        return [record.as_restaurant() for record in self.load_records()]

    def load_records(self) -> list[RestaurantRecord]:
        """Read complete records, including menus, without rewriting legacy data."""
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

        return self._validate_records(records)

    def get_record(self, restaurant_id: str) -> RestaurantRecord | None:
        """Return the complete stored record with this ID, or None if none matches."""
        for record in self.load_records():
            if record.id == restaurant_id:
                return record
        return None

    def mutate_records(
        self, change: Callable[[list[RestaurantRecord]], None]
    ) -> list[RestaurantRecord]:
        """Persist a locked mutation and return the validated records that were saved."""
        with _mutation_lock:
            records = self.load_records()
            change(records)
            validated = self._validate_records(records)
            self._save_records(validated)
            return validated

    def _validate_records(
        self, records: list[RestaurantRecord] | list[object]
    ) -> list[RestaurantRecord]:
        try:
            validated = [
                RestaurantRecord.model_validate(
                    record.model_dump() if isinstance(record, RestaurantRecord) else record
                )
                for record in records
            ]
        except ValidationError as exc:
            raise RestaurantDataError(
                f"Invalid restaurant record in {self.path}: {exc}"
            ) from exc

        restaurant_ids: set[str] = set()
        for record in validated:
            if record.id in restaurant_ids:
                raise RestaurantDataError(f"Duplicate restaurant ID in {self.path}")
            restaurant_ids.add(record.id)
            item_ids: set[str] = set()
            for item in record.menu_items:
                if item.id in item_ids:
                    raise RestaurantDataError(f"Duplicate menu item ID in {self.path}")
                item_ids.add(item.id)
        return validated

    def _save_records(self, records: list[RestaurantRecord]) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(
                    [record.model_dump(mode="json") for record in records],
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                )
                temporary_file.write("\n")
            os.replace(temporary_path, self.path)
        except (OSError, UnicodeError, TypeError) as exc:
            raise RestaurantDataError(
                f"Could not save restaurant data to {self.path}: {exc}"
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
