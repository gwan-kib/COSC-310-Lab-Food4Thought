"""Expose Food4Thought's signed-in customer order history through the shared auth boundary.
Compose the real stores and translate service failures into safe HTTP responses.
"""

from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import CurrentCustomer, authentication_required
from app.repositories.customer import CustomerDataError, CustomerRepository
from app.repositories.order import OrderDataError, OrderRepository
from app.schemas.customer import Principal
from app.schemas.order import Order
from app.schemas.restaurant import ErrorResponse
from app.services.auth import AuthenticationRequiredError
from app.services.order_history import (
    OrderHistoryNotPermittedError, OrderHistoryService, require_history_customer,
)

router = APIRouter(prefix="/customers/me/orders", tags=["orders"])


def get_order_history_service() -> OrderHistoryService[Principal]:
    return OrderHistoryService(partial(require_history_customer, customers=CustomerRepository()),
                               OrderRepository())


Service = Annotated[OrderHistoryService[Principal], Depends(get_order_history_service)]


@router.get("", response_model=list[Order], summary="Read my order history", responses={
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token, or customer no longer exists"},
    403: {"model": ErrorResponse, "description": "Caller is not a customer"},
    500: {"model": ErrorResponse, "description": "Authentication, customer or order data is unavailable"},
})
def list_my_orders(principal: CurrentCustomer, service: Service) -> list[Order]:
    """Saved snapshots in persisted insertion order, or an empty array. Inactive customers retain access."""
    try:
        return service.list_orders(principal)
    except AuthenticationRequiredError:
        raise authentication_required() from None
    except OrderHistoryNotPermittedError:
        raise HTTPException(403, "Operation not permitted") from None
    except CustomerDataError:
        raise HTTPException(500, "Customer data is unavailable") from None
    except OrderDataError:
        raise HTTPException(500, "Order data is unavailable") from None
