"""Provide Food4Thought's #78 authentication handoff models and isolated account data.
Feature owners use these stored-record shapes and fixture accounts to build and test
registration, login and access checks; no application module imports this file.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pwdlib import PasswordHash
from pydantic import ConfigDict, StringConstraints, model_validator

from .m2 import ContractModel, Customer, Identifier

# Tests inject this clock instead of reading the real time (TESTING.md).
FIXED_NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
SESSION_LIFETIME = timedelta(hours=24)

Role = Literal["customer", "restaurant_user", "administrator"]
AccountType = Literal["customer", "staff"]
TokenDigest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Principal(ContractModel):
    """Trusted caller identity produced by authentication, never by a request body."""

    model_config = ConfigDict(frozen=True)

    account_id: Identifier
    role: Role


class StoredCustomer(Customer):
    """Complete customers.json record; only `public()` may leave the backend."""

    role: Literal["customer"]
    password_hash: Identifier

    def public(self) -> Customer:
        return Customer.model_validate(self.model_dump(exclude={"role", "password_hash"}))


class StaffAccount(ContractModel):
    """Provisioned restaurant user or administrator; there is no public sign-up."""

    id: Identifier
    name: Identifier
    email: Identifier
    role: Literal["restaurant_user", "administrator"]
    restaurant_ids: list[Identifier]
    password_hash: Identifier

    @model_validator(mode="after")
    def ownership_matches_role(self) -> Self:
        if self.role == "administrator" and self.restaurant_ids:
            raise ValueError("Administrators do not own restaurants in M2")
        if len(set(self.restaurant_ids)) != len(self.restaurant_ids):
            raise ValueError("Each owned restaurant is listed once")
        return self


class SessionRecord(ContractModel):
    """sessions.json record: the token's SHA-256 digest, never the token itself."""

    token_sha256: TokenDigest
    account_id: Identifier
    account_type: AccountType
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def expires_after_issue(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("A session must expire after it is issued")
        return self


def token_digest(token: str) -> str:
    """Tokens are long random values, so a fast digest suffices for lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FixtureAccount:
    record: StoredCustomer | StaffAccount
    account_type: AccountType
    password: str
    token: str


@dataclass
class AuthFixture:
    paths: dict[str, Path]
    accounts: dict[str, FixtureAccount]
    expired_token: str
    now: datetime = field(default=FIXED_NOW)

    def headers(self, key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.accounts[key].token}"}


# Dummy test-only credentials. They protect nothing and must never seed data/.
_PASSWORDS = {
    "customer_a": "ada-fixture-password-1",
    "customer_b": "ben-fixture-password-2",
    "restaurant_user": "owner-fixture-password-3",
    "administrator": "admin-fixture-password-4",
}


@lru_cache(maxsize=1)
def _password_hashes() -> dict[str, str]:
    # Argon2 is deliberately slow, so hash each dummy password once per run.
    hasher = PasswordHash.recommended()
    return {key: hasher.hash(password) for key, password in _PASSWORDS.items()}


def _write(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def build_auth_fixture(paths: dict[str, Path]) -> AuthFixture:
    """Write two customers, a restaurant user, an administrator and their sessions."""
    hashes = _password_hashes()
    records: dict[str, StoredCustomer | StaffAccount] = {
        "customer_a": StoredCustomer(
            id="customer-001", name="Ada Example", email="ada@example.invalid",
            delivery_address="101 Example Street, Kelowna, BC", status="active",
            role="customer", password_hash=hashes["customer_a"],
        ),
        # Mixed case exercises case-insensitive email lookup and uniqueness.
        "customer_b": StoredCustomer(
            id="customer-002", name="Ben Example", email="Ben.Example@Example.invalid",
            delivery_address="202 Sample Road, Kelowna, BC", status="active",
            role="customer", password_hash=hashes["customer_b"],
        ),
        "restaurant_user": StaffAccount(
            id="staff-001", name="Cedar Bowl Owner", email="owner@example.invalid",
            role="restaurant_user", restaurant_ids=["restaurant-001"],
            password_hash=hashes["restaurant_user"],
        ),
        "administrator": StaffAccount(
            id="staff-002", name="Platform Administrator", email="admin@example.invalid",
            role="administrator", restaurant_ids=[], password_hash=hashes["administrator"],
        ),
    }
    accounts = {
        key: FixtureAccount(
            record=record,
            account_type="customer" if isinstance(record, StoredCustomer) else "staff",
            password=_PASSWORDS[key],
            token=f"fixture-token-{key}-not-a-real-secret",
        )
        for key, record in records.items()
    }
    expired_token = "fixture-token-customer_a-expired"

    def session(token: str, account: FixtureAccount, issued_at: datetime) -> dict:
        return SessionRecord(
            token_sha256=token_digest(token), account_id=account.record.id,
            account_type=account.account_type, issued_at=issued_at,
            expires_at=issued_at + SESSION_LIFETIME,
        ).model_dump(mode="json")

    _write(paths["customers"], [account.record.model_dump(mode="json")
                                for account in accounts.values()
                                if account.account_type == "customer"])
    _write(paths["staff"], [account.record.model_dump(mode="json")
                            for account in accounts.values()
                            if account.account_type == "staff"])
    _write(paths["sessions"], [
        *(session(account.token, account, FIXED_NOW - timedelta(hours=1))
          for account in accounts.values()),
        session(expired_token, accounts["customer_a"],
                FIXED_NOW - SESSION_LIFETIME - timedelta(hours=1)),
    ])
    return AuthFixture(paths=paths, accounts=accounts, expired_token=expired_token)
