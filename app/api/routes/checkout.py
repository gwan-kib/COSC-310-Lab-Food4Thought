"""Expose Food4Thought checkout for the signed-in active customer.
Map the checkout service's durable purchase and replay results to HTTP responses.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.auth import ActiveCustomer, authentication_required
from app.repositories.cart import CartRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.schemas.customer import Principal
from app.schemas.order import CheckoutRequest, CheckoutResponse
from app.schemas.restaurant import ErrorResponse
from app.services.catalog import RestaurantCatalog
from app.services.checkout import CartNotFound, CheckoutConflict, CheckoutDataError, CheckoutService
from app.services.customer import CustomerInactiveError, CustomerNotFoundError, CustomerService

router = APIRouter(tags=["orders"])


def get_checkout_service() -> CheckoutService[Principal]:
    return CheckoutService(
        require_active_customer=CustomerService(CustomerRepository()).active_customer_for,
        carts=CartRepository(), catalog=RestaurantCatalog(), orders=OrderRepository(),
    )


@router.post("/customers/me/checkout", status_code=status.HTTP_201_CREATED,
             response_model=CheckoutResponse, summary="Check out my cart", responses={
                 201: {"description": "New order saved"},
                 200: {"model": CheckoutResponse, "description": "Previously saved order for this cart revision"},
                 401: {"model": ErrorResponse, "description": "Authentication required",
                       "headers": {"WWW-Authenticate": {"schema": {"type": "string"}, "description": "Bearer"}}},
                 403: {"model": ErrorResponse, "description": "Wrong role or inactive customer"},
                 404: {"model": ErrorResponse, "description": "No matching cart owned by this customer"},
                 409: {"model": ErrorResponse, "description": "Empty cart, stale revision or unavailable item"},
                 500: {"model": ErrorResponse, "description": "Authentication, customer or checkout data unavailable"},
             })
def checkout(request: CheckoutRequest, principal: ActiveCustomer, response: Response,
             service: Annotated[CheckoutService[Principal], Depends(get_checkout_service)]) -> CheckoutResponse:
    """Purchase at current menu prices, or replay the receipt for the same cart ID and revision.

    If cart_reset_pending is true, the order is saved. Repeat the original request to finish the reset.
    """
    try:
        result = service.checkout(principal, request)
    except CustomerNotFoundError:
        raise authentication_required() from None
    except CustomerInactiveError:
        raise HTTPException(403, "Customer is inactive") from None
    except CartNotFound:
        raise HTTPException(404, "Cart not found") from None
    except CheckoutConflict as error:
        raise HTTPException(409, str(error)) from None
    except CheckoutDataError:
        raise HTTPException(500, "Checkout data is unavailable") from None
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result.response
