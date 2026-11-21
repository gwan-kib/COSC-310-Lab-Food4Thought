"""Sign Food4Thought users in and resolve their bearer tokens (#80, AUTH_DESIGN.md).
One login serves customers and provisioned staff; it checks the password hash and
stores only the new token's digest. Resolving a token answers "who is calling?" and
leaves role and status decisions to callers.
"""

from datetime import datetime, timedelta

from app.core.security import (
    UnusablePasswordHashError, new_token, token_digest, verify_against_dummy, verify_password,
)
from app.repositories.customer import CustomerDataError, CustomerRepository, SessionRepository
from app.repositories.staff import StaffDataError, StaffRepository
from app.schemas.customer import LoginRequest, LoginResponse, Principal, SessionRecord

SESSION_LIFETIME = timedelta(hours=24)


class InvalidCredentialsError(Exception):
    """Unknown email or wrong password; deliberately indistinguishable."""


class AuthenticationRequiredError(Exception):
    """The token is missing, unknown or expired, or its account no longer exists."""


class AuthService:
    def __init__(self, customers: CustomerRepository, sessions: SessionRepository,
                 staff: StaffRepository | None = None) -> None:
        self.customers = customers
        self.sessions = sessions
        self.staff = staff or StaffRepository()

    def login(self, request: LoginRequest, now: datetime) -> LoginResponse:
        # Emails are unique across both stores, so at most one account matches.
        customer = self.customers.find_by_email(request.email)
        if customer is not None:
            account_id, account_type, role = customer.id, "customer", customer.role
            password_hash, data_error = customer.password_hash, CustomerDataError
        else:
            staff = self.staff.find_by_email(request.email)
            if staff is None:
                verify_against_dummy(request.password)
                raise InvalidCredentialsError()
            account_id, account_type, role = staff.id, "staff", staff.role
            password_hash, data_error = staff.password_hash, StaffDataError
        try:
            matches = verify_password(request.password, password_hash)
        except UnusablePasswordHashError as exc:
            raise data_error(f"Stored password hash for {account_id} is unusable") from exc
        if not matches:
            raise InvalidCredentialsError()
        # Inactive customers may sign in for read-only access (agreed policy).
        token = new_token()
        self.sessions.add_session(SessionRecord(
            token_sha256=token_digest(token), account_id=account_id, account_type=account_type,
            issued_at=now, expires_at=now + SESSION_LIFETIME,
        ))
        return LoginResponse(access_token=token, token_type="bearer", role=role)

    def resolve(self, token: str, now: datetime) -> Principal:
        session = self.sessions.find(token_digest(token))
        if session is None or session.expires_at <= now:
            raise AuthenticationRequiredError()
        if session.account_type == "customer":
            customer = self.customers.get_customer(session.account_id)
            if customer is None:
                raise AuthenticationRequiredError()
            return Principal(account_id=customer.id, role=customer.role)
        staff = self.staff.get_staff(session.account_id)
        if staff is None:
            raise AuthenticationRequiredError()
        return Principal(account_id=staff.id, role=staff.role)
