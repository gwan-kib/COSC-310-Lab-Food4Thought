"""Authorize reads of Food4Thought's historical order snapshots.
Check current customer identity and ownership without repricing the transaction
or requiring its original cart and catalog entries to remain unchanged.
"""

from app.core.workflow import workflow_lock
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.schemas.customer import Principal
from app.schemas.order import Order
from app.services.auth import AuthenticationRequiredError


class OrderAccessDeniedError(Exception):
    """Only customer principals may read customer order details."""


class OrderNotFoundError(Exception):
    """Missing and foreign order identifiers deliberately have the same outcome."""


class OrderDetailsService:
    def __init__(self, customers: CustomerRepository, orders: OrderRepository) -> None:
        self.customers = customers
        self.orders = orders

    def get_order(self, principal: Principal, order_id: str) -> Order:
        """Return an owned snapshot; inactive customers retain read-only access."""
        if principal.role != "customer":
            raise OrderAccessDeniedError("Operation not permitted")
        with workflow_lock:
            # Recheck existence even if the route authenticated earlier. Deactivation
            # preserves identity, so the active-only checkout resolver does not apply.
            customer = self.customers.get_customer(principal.account_id)
            if customer is None:
                raise AuthenticationRequiredError()
            order = self.orders.get_order(order_id)
            if order is None or order.customer_id != customer.id:
                raise OrderNotFoundError("Order not found")
            return order
