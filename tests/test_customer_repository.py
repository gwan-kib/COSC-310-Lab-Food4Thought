"""Check Food4Thought's customer and session repositories without the API (#79/#80).
They must keep emails unique ignoring case, reject corrupt files instead of treating
them as empty, and leave the previous file in place when a save fails.
"""

import json

import pytest

from app.repositories.customer import (
    CustomerDataError, CustomerRepository, DuplicateEmailError, SessionDataError, SessionRepository,
)
from app.schemas.customer import StoredCustomer


def _customer(customer_id, email):
    return StoredCustomer(id=customer_id, name="Example", email=email, delivery_address="1 Street",
                          status="active", role="customer", password_hash="$argon2id$dummy")


def test_added_customer_reloads_from_a_fresh_repository(m2_store_paths):
    CustomerRepository().add_customer(_customer("c-1", "Mixed@Case.invalid"))

    assert CustomerRepository().get_customer("c-1").email == "Mixed@Case.invalid"
    assert CustomerRepository().find_by_email("  mixed@case.INVALID ").id == "c-1"


def test_duplicate_email_ignoring_case_is_rejected_without_a_write(m2_store_paths):
    repository = CustomerRepository()
    repository.add_customer(_customer("c-1", "a@b.invalid"))
    before = m2_store_paths["customers"].read_bytes()

    with pytest.raises(DuplicateEmailError):
        repository.add_customer(_customer("c-2", "A@B.INVALID"))

    assert m2_store_paths["customers"].read_bytes() == before


@pytest.mark.parametrize("content", ["{oops", "{}", json.dumps([{"id": "c-1"}])])
def test_corrupt_customer_file_is_an_error(m2_store_paths, content):
    m2_store_paths["customers"].write_text(content, encoding="utf-8")
    with pytest.raises(CustomerDataError):
        CustomerRepository().get_customer("c-1")


def test_corrupt_session_file_is_an_error(m2_store_paths):
    m2_store_paths["sessions"].write_text('[{"token_sha256": "short"}]', encoding="utf-8")
    with pytest.raises(SessionDataError):
        SessionRepository().find("0" * 64)
