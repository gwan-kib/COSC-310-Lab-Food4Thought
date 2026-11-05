"""Check Food4Thought's #78 authentication fixtures before feature owners rely on them.
They must give two customers and the source-defined staff roles realistic, isolated
stored records without placing a usable password or bearer token in any file.
"""

import json
import os
from pathlib import Path

import pytest
from pwdlib import PasswordHash
from pydantic import ValidationError

from .auth import (
    FIXED_NOW, Principal, SessionRecord, StaffAccount, StoredCustomer, token_digest,
)
from .m2 import Customer

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
AUTH_STORES = ("customers", "staff", "sessions")


def _records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_auth_stores_are_isolated_and_configured(auth_accounts, tmp_path):
    for store in AUTH_STORES:
        path = auth_accounts.paths[store]
        assert path.parent == tmp_path
        assert DATA_DIR not in path.parents
        assert os.environ[f"{store.upper()}_DATA_PATH"] == str(path)


def test_two_distinct_active_customers_have_safe_public_views(auth_accounts):
    customers = [StoredCustomer.model_validate(record)
                 for record in _records(auth_accounts.paths["customers"])]
    staff = [StaffAccount.model_validate(record)
             for record in _records(auth_accounts.paths["staff"])]

    assert len(customers) == 2
    assert len({customer.id for customer in customers}) == 2
    assert {customer.status for customer in customers} == {"active"}
    emails = [account.email.casefold() for account in [*customers, *staff]]
    assert len(set(emails)) == len(emails)
    for customer in customers:
        public = customer.public()
        assert isinstance(public, Customer)
        assert set(public.model_dump()) == {"id", "name", "email", "delivery_address", "status"}


def test_passwords_and_tokens_never_appear_in_stored_files(auth_accounts):
    stored_text = "".join(path.read_text(encoding="utf-8")
                          for path in auth_accounts.paths.values())
    for account in auth_accounts.accounts.values():
        assert account.password not in stored_text
        assert account.token not in stored_text
    assert auth_accounts.expired_token not in stored_text


def test_stored_hashes_are_argon2id_and_verify_only_their_own_password(auth_accounts):
    hasher = PasswordHash.recommended()
    accounts = list(auth_accounts.accounts.values())
    for account in accounts:
        assert account.record.password_hash.startswith("$argon2id$")
        assert hasher.verify(account.password, account.record.password_hash)
        others = [other.password for other in accounts if other is not account]
        assert not any(hasher.verify(other, account.record.password_hash) for other in others)


def test_restaurant_user_owns_an_existing_restaurant_and_administrator_owns_none(auth_accounts):
    restaurant_ids = {record["id"] for record in _records(auth_accounts.paths["restaurants"])}
    owner = auth_accounts.accounts["restaurant_user"].record
    admin = auth_accounts.accounts["administrator"].record

    assert owner.role == "restaurant_user"
    assert owner.restaurant_ids and set(owner.restaurant_ids) <= restaurant_ids
    assert admin.role == "administrator"
    assert admin.restaurant_ids == []


def test_sessions_store_only_digests_with_server_side_expiry(auth_accounts):
    sessions = [SessionRecord.model_validate_json(json.dumps(record))
                for record in _records(auth_accounts.paths["sessions"])]
    by_digest = {session.token_sha256: session for session in sessions}

    for account in auth_accounts.accounts.values():
        session = by_digest[token_digest(account.token)]
        assert session.account_id == account.record.id
        assert session.account_type == account.account_type
        assert session.expires_at > FIXED_NOW
    expired = by_digest[token_digest(auth_accounts.expired_token)]
    assert expired.account_id == auth_accounts.accounts["customer_a"].record.id
    assert expired.expires_at <= FIXED_NOW
    assert len(by_digest) == len(sessions)


def test_principal_is_immutable_and_limited_to_source_roles():
    principal = Principal(account_id="customer-001", role="customer")
    with pytest.raises(ValidationError):
        principal.role = "administrator"
    with pytest.raises(ValidationError):
        Principal(account_id="driver-001", role="driver")


def test_authorization_header_helper_uses_the_bearer_scheme(auth_accounts):
    account = auth_accounts.accounts["customer_b"]
    assert auth_accounts.headers("customer_b") == {"Authorization": f"Bearer {account.token}"}
