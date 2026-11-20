"""Define Food4Thought's customer account models: registration, profile updates,
the public profile, the stored record with its password hash, and sign-in sessions.
Only `Customer` may leave the backend; the stored record never reaches a response.
"""

from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator,
)
from pydantic.json_schema import SkipJsonSchema

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# Case-sensitive and never trimmed (AUTH_DESIGN.md agreed policy).
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Role = Literal["customer", "restaurant_user", "administrator"]


def check_email(value: str) -> str:
    """One nonempty local part and domain around a single "@", no spaces or control characters."""
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Email must not contain spaces or control characters")
    local, at, domain = value.partition("@")
    if not at or not local or not domain or "@" in domain:
        raise ValueError("Email must look like name@domain")
    return value


Email = Annotated[Text, AfterValidator(check_email)]


class CustomerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CustomerRegistration(CustomerModel):
    """POST /customers body. Role, status and ID are server-owned, so they are rejected."""

    name: Text
    email: Email
    delivery_address: Text
    password: Password


class CustomerProfileUpdate(CustomerModel):
    """PATCH /customers/me body: only name and delivery address, at least one, no nulls."""

    name: Text | SkipJsonSchema[None] = Field(default=None)
    delivery_address: Text | SkipJsonSchema[None] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def no_explicit_nulls(cls, data: object) -> object:
        if isinstance(data, dict) and any(value is None for value in data.values()):
            raise ValueError("Profile fields cannot be null")
        return data

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide name or delivery_address")
        return self


class Customer(CustomerModel):
    """Public customer profile returned by the API."""

    id: Text
    name: Text
    email: Text
    delivery_address: Text
    status: Literal["active", "inactive"]


class StoredCustomer(Customer):
    """Complete customers.json record."""

    role: Literal["customer"]
    password_hash: Text

    def public(self) -> Customer:
        return Customer.model_validate(self.model_dump(exclude={"role", "password_hash"}))


class LoginRequest(CustomerModel):
    email: Text
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class LoginResponse(CustomerModel):
    access_token: str
    token_type: Literal["bearer"]
    role: Role


class Principal(CustomerModel):
    """Trusted caller identity produced by authentication, never by a request body."""

    model_config = ConfigDict(frozen=True)

    account_id: Text
    role: Role


class SessionRecord(CustomerModel):
    """sessions.json record: the token's SHA-256 digest, never the token itself."""

    # Not strict: timestamps are ISO strings once they have been stored as JSON.
    model_config = ConfigDict(extra="forbid", strict=False)

    token_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    account_id: Text
    account_type: Literal["customer", "staff"]
    # Timezone-aware, so comparing with the clock can never raise mid-request.
    issued_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def expires_after_issue(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("A session must expire after it is issued")
        return self
