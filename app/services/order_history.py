"""Read Food4Thought order history for the customer authorized by the shared helper.
Reuse saved snapshots without consulting or changing current carts or menu data.
"""

from collections.abc import Callable
from typing import Protocol

from app.core.workflow import workflow_lock
from app.repositories.order import OrderRepository
from app.schemas.order import Order


class Customer(Protocol):
    id: str


class OrderHistoryService[Principal]:
    def __init__(self, require_customer: Callable[[Principal], Customer],
                 orders: OrderRepository) -> None:
        # Bind #84's shared helper to its customer store and active=False.
        self.require_customer = require_customer
        self.orders = orders

    def list_orders(self, principal: Principal) -> list[Order]:
        """Return persisted insertion order; propagate access and storage failures."""
        with workflow_lock:
            customer = self.require_customer(principal)
            return self.orders.list_for_customer(customer.id)
