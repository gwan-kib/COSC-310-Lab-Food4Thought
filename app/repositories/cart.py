"""Persist Food4Thought's active carts in JSON, one per customer, with stable IDs.
Reads validate every record; writes hold a repository lock and use the shared
json_file helper, so a failed save leaves the previous carts intact.
"""

from collections.abc import Callable
from pathlib import Path
from threading import Lock
from uuid import uuid4

from pydantic import ValidationError

from app.core.config import get_carts_data_path
from app.core.json_file import read_json_array, write_json_array
from app.core.storage import StorageFailure
from app.schemas.cart import CartRecord

_mutation_lock = Lock()
class CartDataError(StorageFailure):
    """Cart data could not be read, validated or saved."""


class CartRepository:
    """Load and atomically replace cart records; business rules live in CartService."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_carts_data_path()

    def load_carts(self) -> list[CartRecord]:
        return self._validate(read_json_array(self.path, CartDataError))

    def get_cart(self, customer_id: str) -> CartRecord | None:
        return next((cart for cart in self.load_carts() if cart.customer_id == customer_id), None)

    def create_cart(
        self, customer_id: str, before_save: Callable[[CartRecord], None] | None = None
    ) -> tuple[CartRecord, bool]:
        """Return the customer's cart, creating an empty one if none exists yet.

        `before_save` runs on a new cart before it is written; if it raises, nothing is saved.
        """
        created: list[CartRecord] = []

        def add_if_missing(carts: list[CartRecord]) -> None:
            if any(cart.customer_id == customer_id for cart in carts):
                return
            existing_ids = {cart.id for cart in carts}
            cart_id = str(uuid4())
            while cart_id in existing_ids:
                cart_id = str(uuid4())
            created.append(CartRecord(id=cart_id, customer_id=customer_id, revision=0,
                                      restaurant_id=None, items=[]))
            if before_save is not None:
                before_save(created[0])
            carts.append(created[0])

        carts = self._mutate(add_if_missing, save=lambda: bool(created))
        cart = next(cart for cart in carts if cart.customer_id == customer_id)
        return cart, bool(created)

    def save_cart(self, cart: CartRecord) -> None:
        """Replace the stored cart that has the same ID and customer."""

        def replace(carts: list[CartRecord]) -> None:
            for index, stored in enumerate(carts):
                if (stored.id, stored.customer_id) == (cart.id, cart.customer_id):
                    carts[index] = cart
                    return
            raise CartDataError(f"Cart {cart.id} is not stored in {self.path}")

        self._mutate(replace)

    def reset_after_order(self, customer_id: str, cart_id: str, expected_revision: int) -> bool:
        """Empty the cart only if it is still the purchased revision (used by checkout)."""
        matched: list[bool] = []

        def reset(carts: list[CartRecord]) -> None:
            for index, cart in enumerate(carts):
                if (cart.customer_id, cart.id, cart.revision) == (customer_id, cart_id, expected_revision):
                    carts[index] = CartRecord(id=cart.id, customer_id=customer_id,
                                              revision=cart.revision + 1, restaurant_id=None, items=[])
                    matched.append(True)

        self._mutate(reset, save=lambda: bool(matched))
        return bool(matched)

    def _mutate(self, change: Callable[[list[CartRecord]], None],
                save: Callable[[], bool] = lambda: True) -> list[CartRecord]:
        with _mutation_lock:
            carts = self.load_carts()
            change(carts)
            validated = self._validate([cart.model_dump() for cart in carts])
            if save():
                self._save(validated)
            return validated

    def _validate(self, records: list[object]) -> list[CartRecord]:
        try:
            carts = [CartRecord.model_validate(record) for record in records]
        except ValidationError as exc:
            raise CartDataError(f"Invalid cart record in {self.path}: {exc}") from exc
        return self._check_unique(carts)

    def _check_unique(self, carts: list[CartRecord]) -> list[CartRecord]:
        if len({cart.id for cart in carts}) != len(carts):
            raise CartDataError(f"Duplicate cart ID in {self.path}")
        if len({cart.customer_id for cart in carts}) != len(carts):
            raise CartDataError(f"More than one active cart for a customer in {self.path}")
        return carts

    def _save(self, carts: list[CartRecord]) -> None:
        write_json_array(self.path, [cart.model_dump() for cart in carts], CartDataError)
