"""Expose Food4Thought's customer account endpoints: register (#79), sign in (#80),
read or update the signed-in customer's own profile (#81/#82), and deactivate it (#83). Routes translate
service outcomes to HTTP; account rules live in the customer and auth services.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import ActiveCustomer, CurrentCustomer, authentication_required, get_now
from app.core.storage import StorageFailure
from app.repositories.customer import CustomerRepository, SessionDataError, SessionRepository
from app.schemas.customer import Customer, CustomerProfileUpdate, CustomerRegistration, LoginRequest, LoginResponse
from app.schemas.restaurant import ErrorResponse
from app.services.auth import AuthService, InvalidCredentialsError
from app.services.customer import (
    CustomerInactiveError, CustomerNotFoundError, CustomerService, DuplicateEmailError,
)

router = APIRouter(tags=["customers"])

CUSTOMER_DATA_ERROR = "Customer data is unavailable"
AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired bearer token"},
    403: {"model": ErrorResponse, "description": "Not a customer, or customer is inactive"},
    500: {"model": ErrorResponse, "description": "Customer or authentication data is unavailable"},
}


def get_customer_service() -> CustomerService:
    return CustomerService(CustomerRepository())


Service = Annotated[CustomerService, Depends(get_customer_service)]


@router.post("/customers", response_model=Customer, status_code=status.HTTP_201_CREATED,
             summary="Register a customer",
             responses={409: {"model": ErrorResponse, "description": "Email is already registered"},
                        500: {"model": ErrorResponse, "description": CUSTOMER_DATA_ERROR}})
def register_customer(request: CustomerRegistration, service: Service) -> Customer:
    """Create an active customer. The password is stored only as an Argon2id hash."""
    try:
        return service.register(request)
    except DuplicateEmailError:
        raise HTTPException(409, "Email is already registered") from None
    except StorageFailure:
        raise HTTPException(500, CUSTOMER_DATA_ERROR) from None


@router.post("/auth/login", response_model=LoginResponse, tags=["auth"], summary="Sign in",
             responses={401: {"model": ErrorResponse, "description": "Invalid email or password"},
                        500: {"model": ErrorResponse, "description": "Authentication data is unavailable"}})
def login(request: LoginRequest, now: Annotated[datetime, Depends(get_now)]) -> LoginResponse:
    """Return a bearer token valid for 24 hours. Send it as `Authorization: Bearer <token>`."""
    try:
        return AuthService(CustomerRepository(), SessionRepository()).login(request, now)
    except InvalidCredentialsError:
        raise HTTPException(401, "Invalid email or password",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    except SessionDataError:
        raise HTTPException(500, "Authentication data is unavailable") from None
    except StorageFailure:
        raise HTTPException(500, CUSTOMER_DATA_ERROR) from None


@router.get("/customers/me", response_model=Customer, summary="Read my profile", responses=AUTH_ERRORS)
def read_my_profile(principal: CurrentCustomer, service: Service) -> Customer:
    """Inactive customers can still read their profile."""
    try:
        return service.get_profile(principal.account_id)
    except CustomerNotFoundError:
        raise authentication_required() from None
    except StorageFailure:
        raise HTTPException(500, CUSTOMER_DATA_ERROR) from None


@router.patch("/customers/me", response_model=Customer, summary="Update my name or delivery address",
              responses=AUTH_ERRORS)
def update_my_profile(principal: ActiveCustomer, request: CustomerProfileUpdate, service: Service) -> Customer:
    """Change `name` and/or `delivery_address`. Other fields are rejected with 422."""
    try:
        return service.update_profile(principal.account_id, request)
    except CustomerNotFoundError:
        raise authentication_required() from None
    except CustomerInactiveError:
        raise HTTPException(403, "Customer is inactive") from None
    except StorageFailure:
        raise HTTPException(500, CUSTOMER_DATA_ERROR) from None


@router.post("/customers/me/deactivate", response_model=Customer, summary="Deactivate my account",
             responses=AUTH_ERRORS)
def deactivate_my_account(principal: CurrentCustomer, service: Service) -> Customer:
    """Set the account inactive. The ID, cart and orders are kept; there is no reactivation.
    An inactive customer can still sign in and read, but cannot change the cart or check out."""
    try:
        return service.deactivate(principal.account_id)
    except CustomerNotFoundError:
        raise authentication_required() from None
    except StorageFailure:
        raise HTTPException(500, CUSTOMER_DATA_ERROR) from None
