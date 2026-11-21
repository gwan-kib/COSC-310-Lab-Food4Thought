"""Read Food4Thought order history for the customer authorized by the shared helper.
Reuse saved snapshots without consulting or changing current carts or menu data.
"""

from collections.abc import Callable
from typing import Protocol

from app.core.workflow import workflow_lock
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.schemas.customer import Customer as PublicCustomer, Principal as CustomerPrincipal
from app.schemas.order import Order
from app.services.auth import AuthenticationRequiredError


class OrderHistoryNotPermittedError(Exception):
    """Only a customer can retrieve their order history."""


def require_history_customer(principal: CustomerPrincipal, *, customers: CustomerRepository) -> PublicCustomer:
    """Resolve read access inside the history service's workflow lock, including inactive customers."""
    if principal.role != "customer":
        raise OrderHistoryNotPermittedError()
    customer = customers.get_customer(principal.account_id)
    if customer is None:
        raise AuthenticationRequiredError()
    return customer.public()


class Customer(Protocol):
    id: str


class OrderHistoryService[Principal]:
    def __init__(self, require_customer: Callable[[Principal], Customer],
                 orders: OrderRepository) -> None:
        # Production binds require_history_customer to the merged customer store.
        self.require_customer = require_customer
        self.orders = orders

    def list_orders(self, principal: Principal) -> list[Order]:
        """Return persisted insertion order; propagate access and storage failures."""
        with workflow_lock:
            customer = self.require_customer(principal)
            return self.orders.list_for_customer(customer.id)
