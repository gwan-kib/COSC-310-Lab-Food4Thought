"""Persist Food4Thought order snapshots and find receipts for repeated checkouts.
Validate the complete store and replace it atomically only after a successful append.
"""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

from pydantic import TypeAdapter, ValidationError

from app.core.config import get_orders_data_path
from app.core.json_file import loads_exact
from app.core.storage import StorageFailure
from app.schemas.order import Order


class OrderDataError(StorageFailure):
    """The order store could not be read, validated or saved."""


_orders = TypeAdapter(list[Order])


_mutation_lock = Lock()


class OrderRepository:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_orders_data_path()

    def _read(self) -> list[Order]:
        try:
            # Parse with exact integers, then apply the same strict Order validation.
            records = _orders.validate_python(loads_exact(self.path.read_bytes()))
        except (OSError, ValueError, ValidationError) as exc:
            raise OrderDataError("Order data is unavailable") from exc
        ids = {order.id for order in records}
        attempts = {(order.source_cart_id, order.source_cart_revision) for order in records}
        if len(ids) != len(records) or len(attempts) != len(records):
            raise OrderDataError("Order data is unavailable")
        return records

    def get_order(self, order_id: str) -> Order | None:
        return next((order for order in self._read() if order.id == order_id), None)

    def list_for_customer(self, customer_id: str) -> list[Order]:
        return [order for order in self._read() if order.customer_id == customer_id]

    def find_for_cart(self, cart_id: str, revision: int) -> Order | None:
        for order in self._read():
            if (order.source_cart_id, order.source_cart_revision) == (cart_id, revision):
                return order
        return None

    def save_order(self, order: Order) -> None:
        with _mutation_lock:
            records = self._read()
            try:
                order = Order.model_validate(order.model_dump())
            except ValidationError as exc:
                raise OrderDataError("Order data is unavailable") from exc
            attempt = (order.source_cart_id, order.source_cart_revision)
            for existing in records:
                existing_attempt = (existing.source_cart_id, existing.source_cart_revision)
                if existing.id == order.id or existing_attempt == attempt:
                    raise OrderDataError("Order data is unavailable")
            records.append(order)
            self._replace(records)

    def _replace(self, records: list[Order]) -> None:
        temporary_path = None
        try:
            with NamedTemporaryFile(dir=self.path.parent, prefix=f".{self.path.name}.",
                                    suffix=".tmp", delete=False) as output:
                temporary_path = Path(output.name)
                output.write(_orders.dump_json(records, indent=2))
                output.write(b"\n")
            os.replace(temporary_path, self.path)
        except OSError as exc:
            raise OrderDataError("Order data is unavailable") from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
