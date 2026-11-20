"""Persist Food4Thought customer accounts and sign-in sessions in JSON files.
Every read validates the whole file; writes run under a lock and replace the file
atomically, so a failed save keeps the previous accounts and sessions.
"""

from collections.abc import Callable
from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from app.core.config import get_customers_data_path, get_sessions_data_path
from app.core.json_file import read_json_array, write_json_array
from app.core.storage import StorageFailure
from app.schemas.customer import SessionRecord, StoredCustomer

# Held for every write that can add an account email. Staff provisioning (#107) must
# hold it too, so a customer and a staff account cannot claim the same email at once.
ACCOUNT_EMAIL_LOCK = Lock()
_session_lock = Lock()


class CustomerDataError(StorageFailure):
    """Customer data could not be read, validated or saved."""


class SessionDataError(StorageFailure):
    """Session data could not be read, validated or saved."""


class DuplicateEmailError(Exception):
    """Another account already uses this email, ignoring case."""


class CustomerRepository:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_customers_data_path()

    def load_customers(self) -> list[StoredCustomer]:
        return self._validate(read_json_array(self.path, CustomerDataError))

    def get_customer(self, customer_id: str) -> StoredCustomer | None:
        return next((c for c in self.load_customers() if c.id == customer_id), None)

    def find_by_email(self, email: str) -> StoredCustomer | None:
        wanted = email.strip().casefold()
        return next((c for c in self.load_customers() if c.email.casefold() == wanted), None)

    def add_customer(self, customer: StoredCustomer,
                     reserved_emails: Callable[[], set[str]] = set) -> None:
        """Add a customer; `reserved_emails` returns other accounts' casefolded emails."""
        def add(customers: list[StoredCustomer]) -> None:
            # Checked again under the lock so two registrations cannot share an email.
            wanted = customer.email.casefold()
            if wanted in reserved_emails() or any(c.email.casefold() == wanted for c in customers):
                raise DuplicateEmailError(customer.email)
            customers.append(customer)

        self._mutate(add)

    def save_customer(self, customer: StoredCustomer) -> None:
        def replace(customers: list[StoredCustomer]) -> None:
            for index, stored in enumerate(customers):
                if stored.id == customer.id:
                    customers[index] = customer
                    return
            raise CustomerDataError(f"Customer {customer.id} is not stored in {self.path}")

        self._mutate(replace)

    def _mutate(self, change: Callable[[list[StoredCustomer]], None]) -> None:
        with ACCOUNT_EMAIL_LOCK:
            customers = self.load_customers()
            change(customers)
            validated = self._validate([c.model_dump() for c in customers])
            write_json_array(self.path, [c.model_dump(mode="json") for c in validated], CustomerDataError)

    def _validate(self, records: list[object]) -> list[StoredCustomer]:
        try:
            customers = [StoredCustomer.model_validate(record) for record in records]
        except ValidationError as exc:
            raise CustomerDataError(f"Invalid customer record in {self.path}: {exc}") from exc
        if len({c.id for c in customers}) != len(customers):
            raise CustomerDataError(f"Duplicate customer ID in {self.path}")
        if len({c.email.casefold() for c in customers}) != len(customers):
            raise CustomerDataError(f"Duplicate customer email in {self.path}")
        return customers


class SessionRepository:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_sessions_data_path()

    def load_sessions(self) -> list[SessionRecord]:
        records = read_json_array(self.path, SessionDataError)
        try:
            return [SessionRecord.model_validate(record) for record in records]
        except ValidationError as exc:
            raise SessionDataError(f"Invalid session record in {self.path}: {exc}") from exc

    def find(self, token_sha256: str) -> SessionRecord | None:
        return next((s for s in self.load_sessions() if s.token_sha256 == token_sha256), None)

    def add_session(self, session: SessionRecord) -> None:
        with _session_lock:
            sessions = self.load_sessions()
            sessions.append(session)
            write_json_array(self.path, [s.model_dump(mode="json") for s in sessions], SessionDataError)
