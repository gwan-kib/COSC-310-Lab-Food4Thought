"""Expose the signed-in customer's saved order details for Food4Thought.
Authentication uses the shared bearer dependency; ownership and historical read
rules stay in the service, while this route maps domain errors to HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import CurrentCustomer, authentication_required
from app.repositories.customer import CustomerDataError, CustomerRepository
from app.repositories.order import OrderDataError, OrderRepository
from app.schemas.order import Order
from app.schemas.restaurant import ErrorResponse
from app.services.auth import AuthenticationRequiredError
from app.services.order_details import OrderAccessDeniedError, OrderDetailsService, OrderNotFoundError

router = APIRouter(prefix="/customers/me/orders", tags=["orders"])


def get_order_details_service() -> OrderDetailsService:
    return OrderDetailsService(CustomerRepository(), OrderRepository())


Service = Annotated[OrderDetailsService, Depends(get_order_details_service)]


@router.get("/{order_id}", response_model=Order, summary="Get my saved order", responses={
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired identity",
          "headers": {"WWW-Authenticate": {"schema": {"type": "string"}, "description": "Bearer"}}},
    403: {"model": ErrorResponse, "description": "Caller is not a customer"},
    404: {"model": ErrorResponse, "description": "Order is missing or belongs to another customer"},
    500: {"model": ErrorResponse, "description": "Authentication, customer or order data is unavailable"},
})
def get_order(order_id: str, principal: CurrentCustomer, service: Service) -> Order:
    """Return the original snapshot, including prices and delivery address.

    Active and inactive owners can read it. The identifier is opaque (not UUID-only),
    and knowing another customer's identifier does not grant access.
    """
    try:
        return service.get_order(principal, order_id)
    except AuthenticationRequiredError:
        raise authentication_required() from None
    except OrderAccessDeniedError:
        raise HTTPException(403, "Operation not permitted") from None
    except OrderNotFoundError:
        raise HTTPException(404, "Order not found") from None
    except CustomerDataError:
        raise HTTPException(500, "Customer data is unavailable") from None
    except OrderDataError:
        raise HTTPException(500, "Order data is unavailable") from None
