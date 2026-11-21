"""Expose the signed-in customer's cart, item additions, quantity edits, clearing
and backend-calculated totals. Routes require customer authentication, with active
accounts for changes, and delegate cart rules to CartService.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.auth import ActiveCustomer, CurrentCustomer
from app.core.storage import StorageFailure
from app.repositories.cart import CartRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.repositories.restaurant import RestaurantDataError
from app.schemas.cart import AddCartItemRequest, CartView, UpdateCartQuantityRequest
from app.schemas.restaurant import ErrorResponse
from app.services.cart import (
    CartItemNotFoundError, CartNotFoundError, CartRestaurantConflictError, CartService, CheckoutRecoveryRequiredError,
    CustomerInactiveError, CustomerNotFoundError, MenuItemUnavailableError,
)
from app.services.catalog import RestaurantCatalog
from app.services.restaurant import MenuItemNotFoundError, RestaurantNotFoundError

router = APIRouter(prefix="/customers/me/cart", tags=["cart"])


def get_cart_service() -> CartService:
    # Real stores: customer status, current menu prices, and Thomas's order receipts.
    return CartService(carts=CartRepository(), customers=CustomerRepository(),
                       catalog=RestaurantCatalog(), receipts=OrderRepository())


Service = Annotated[CartService, Depends(get_cart_service)]

ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired bearer token"},
    403: {"model": ErrorResponse, "description": "Not a customer, or customer is inactive"},
    404: {"model": ErrorResponse, "description": "Cart, restaurant or menu item not found"},
    409: {"model": ErrorResponse, "description": "Other restaurant, unavailable item, or checkout recovery needed"},
    500: {"model": ErrorResponse, "description": "Cart, customer or restaurant data is unavailable"},
}


def _http_error(error: Exception) -> HTTPException:
    """Translate cart-service outcomes into the M2 contract's status codes and messages."""
    match error:
        case CartNotFoundError():
            return HTTPException(404, "Cart not found")
        case CartItemNotFoundError():
            return HTTPException(404, "Cart item not found")
        case RestaurantNotFoundError():
            return HTTPException(404, "Restaurant not found")
        case MenuItemNotFoundError():
            return HTTPException(404, "Menu item not found")
        case CartRestaurantConflictError():
            return HTTPException(409, "Cart belongs to another restaurant")
        case MenuItemUnavailableError():
            return HTTPException(409, "Menu item is unavailable")
        case CheckoutRecoveryRequiredError():
            return HTTPException(409, "Cart checkout recovery required")
        case CustomerInactiveError():
            return HTTPException(403, "Customer is inactive")
        case CustomerNotFoundError():
            return HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
        case RestaurantDataError():
            return HTTPException(500, "Restaurant data is unavailable")
        case _:
            return HTTPException(500, "Cart data is unavailable")


HANDLED = (CartItemNotFoundError, CartNotFoundError, RestaurantNotFoundError, MenuItemNotFoundError,
           CartRestaurantConflictError, MenuItemUnavailableError, CheckoutRecoveryRequiredError,
           CustomerInactiveError, CustomerNotFoundError, RestaurantDataError, StorageFailure)


@router.put("", response_model=CartView, summary="Create or get my cart",
            responses={200: {"model": CartView, "description": "Existing cart"},
                       201: {"model": CartView, "description": "New empty cart"}, **ERRORS})
def create_or_get_cart(principal: ActiveCustomer, service: Service, response: Response) -> CartView:
    """Return the active cart, creating an empty one the first time (201)."""
    try:
        view, created = service.create_or_get_cart(principal.account_id)
    except HANDLED as error:
        raise _http_error(error) from None
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return view


@router.get("", response_model=CartView, summary="Get my cart and totals", responses=ERRORS)
def get_cart(principal: CurrentCustomer, service: Service) -> CartView:
    """Items priced from the current menu; subtotal and total are calculated by the backend.
    Never creates a cart; inactive customers can still read theirs."""
    try:
        return service.get_cart(principal.account_id)
    except HANDLED as error:
        raise _http_error(error) from None


@router.post("/items", response_model=CartView, summary="Add a menu item to my cart", responses=ERRORS)
def add_item(principal: ActiveCustomer, request: AddCartItemRequest, service: Service) -> CartView:
    """Adding an item already in the cart increases its quantity. Prices come from the menu."""
    try:
        return service.add_item(principal.account_id, request)
    except HANDLED as error:
        raise _http_error(error) from None


@router.patch("/items/{item_id}", response_model=CartView, summary="Set a cart item's quantity",
              responses={**ERRORS,
                         404: {"model": ErrorResponse, "description": "Cart not found or Cart item not found"},
                         409: {"model": ErrorResponse, "description": "Menu item is unavailable or Cart checkout recovery required"}})
def update_quantity(item_id: str, request: UpdateCartQuantityRequest, principal: ActiveCustomer,
                    service: Service) -> CartView:
    """Set an available line to a positive integer quantity and return current menu totals.
    Repeating the same quantity keeps the cart revision. Zero cannot remove a line."""
    try:
        return service.update_quantity(principal.account_id, item_id, request)
    except HANDLED as error:
        raise _http_error(error) from None


@router.delete("/items", response_model=CartView, summary="Clear my shopping cart",
               responses={**ERRORS,
                          404: {"model": ErrorResponse, "description": "Cart not found"},
                          409: {"model": ErrorResponse, "description": "Cart checkout recovery required"}})
def clear_cart(principal: ActiveCustomer, service: Service) -> CartView:
    """Clear all lines, release the restaurant and return zero subtotal/total.

    Preserve cart/customer IDs and increment revision once for a nonempty cart.
    Repeating a clear on an empty cart returns the same view without saving.
    Purchased revisions pending checkout recovery must be recovered through checkout.
    """
    try:
        return service.clear_cart(principal.account_id)
    except HANDLED as error:
        raise _http_error(error) from None
