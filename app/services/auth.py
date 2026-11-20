"""Sign Food4Thought users in and resolve their bearer tokens (#80, AUTH_DESIGN.md).
Login checks the password hash and stores only the new token's digest; resolving a
token answers "who is calling?" and leaves role and status decisions to callers.
"""

from datetime import datetime, timedelta

from pydantic import BaseModel, ValidationError

from app.core.config import get_staff_data_path
from app.core.json_file import read_json_array
from app.core.security import new_token, token_digest, verify_against_dummy, verify_password
from app.repositories.customer import CustomerRepository, SessionDataError, SessionRepository
from app.schemas.customer import LoginRequest, LoginResponse, Principal, Role, SessionRecord

SESSION_LIFETIME = timedelta(hours=24)


class InvalidCredentialsError(Exception):
    """Unknown email or wrong password; deliberately indistinguishable."""


class AuthenticationRequiredError(Exception):
    """The token is missing, unknown or expired, or its account no longer exists."""


class _StaffAccount(BaseModel):
    id: str
    role: Role


class AuthService:
    def __init__(self, customers: CustomerRepository, sessions: SessionRepository) -> None:
        self.customers = customers
        self.sessions = sessions

    def login(self, request: LoginRequest, now: datetime) -> LoginResponse:
        customer = self.customers.find_by_email(request.email)
        if customer is None:
            verify_against_dummy(request.password)
            raise InvalidCredentialsError()
        if not verify_password(request.password, customer.password_hash):
            raise InvalidCredentialsError()
        # Inactive customers may sign in for read-only access (agreed policy).
        token = new_token()
        self.sessions.add_session(SessionRecord(
            token_sha256=token_digest(token), account_id=customer.id, account_type="customer",
            issued_at=now, expires_at=now + SESSION_LIFETIME,
        ))
        return LoginResponse(access_token=token, token_type="bearer", role="customer")

    def resolve(self, token: str, now: datetime) -> Principal:
        session = self.sessions.find(token_digest(token))
        if session is None or session.expires_at <= now:
            raise AuthenticationRequiredError()
        if session.account_type == "customer":
            customer = self.customers.get_customer(session.account_id)
            if customer is None:
                raise AuthenticationRequiredError()
            return Principal(account_id=customer.id, role=customer.role)
        return Principal(account_id=session.account_id, role=self._staff_role(session.account_id))

    def _staff_role(self, staff_id: str) -> Role:
        # Staff accounts are provisioned by #107; only their role is needed here.
        try:
            staff = [_StaffAccount.model_validate(record)
                     for record in read_json_array(get_staff_data_path(), SessionDataError)]
        except ValidationError as exc:
            raise SessionDataError(f"Invalid staff record: {exc}") from exc
        account = next((s for s in staff if s.id == staff_id), None)
        if account is None:
            raise AuthenticationRequiredError()
        return account.role
