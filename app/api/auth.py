"""Resolve the caller for Food4Thought's protected routes (AUTH_DESIGN.md).
`get_current_principal` only answers "who is calling?" (401). The pre-checks add
role and active-status checks that must run before body validation (403); services
repeat the status check under the workflow lock, which stays authoritative.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.storage import StorageFailure
from app.repositories.customer import CustomerRepository, SessionRepository
from app.schemas.customer import Principal
from app.services.auth import AuthenticationRequiredError, AuthService

_bearer = HTTPBearer(auto_error=False, description="Token from POST /auth/login")
UNAUTHENTICATED = {"detail": "Authentication required"}


def get_now() -> datetime:
    """The clock is a dependency so tests can fix it."""
    return datetime.now(timezone.utc)


def get_auth_service() -> AuthService:
    return AuthService(CustomerRepository(), SessionRepository())


def authentication_required() -> HTTPException:
    return HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    now: Annotated[datetime, Depends(get_now)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise authentication_required()
    try:
        return service.resolve(credentials.credentials, now)
    except AuthenticationRequiredError:
        raise authentication_required() from None
    except StorageFailure:
        # Corrupt data must not look like "not signed in".
        raise HTTPException(500, "Authentication data is unavailable") from None


def require_customer(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
    if principal.role != "customer":
        raise HTTPException(403, "Operation not permitted")
    return principal


def require_active_customer(principal: Annotated[Principal, Depends(require_customer)]) -> Principal:
    try:
        customer = CustomerRepository().get_customer(principal.account_id)
    except StorageFailure:
        raise HTTPException(500, "Customer data is unavailable") from None
    if customer is None:
        raise authentication_required()
    if customer.status != "active":
        raise HTTPException(403, "Customer is inactive")
    return principal


CurrentCustomer = Annotated[Principal, Depends(require_customer)]
ActiveCustomer = Annotated[Principal, Depends(require_active_customer)]

def require_restaurant_user(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
    if principal.role != "restaurant_user":
        raise HTTPException(403, "Operation not permitted")
    return principal
