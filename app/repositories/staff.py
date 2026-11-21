"""Store Food4Thought's provisioned staff accounts (restaurant users and administrators).
There is no public staff sign-up: the #107 command writes these records. Every read
validates them strictly, so a damaged record is a storage error, never a wrong role.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from app.core.account_lock import account_email_lock
from app.core.config import get_staff_data_path
from app.core.json_file import read_json_array, write_json_array
from app.core.storage import StorageFailure

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StaffDataError(StorageFailure):
    """Staff data could not be read or validated."""


class StaffAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Text
    name: Text
    email: Text
    # Only staff roles: a record claiming "customer" must not pass customer-route checks.
    role: Literal["restaurant_user", "administrator"]
    restaurant_ids: list[Text]
    password_hash: Text


class StaffRepository:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else get_staff_data_path()

    def load_staff(self) -> list[StaffAccount]:
        records = read_json_array(self.path, StaffDataError)
        try:
            staff = [StaffAccount.model_validate(record) for record in records]
        except ValidationError as exc:
            raise StaffDataError(f"Invalid staff record in {self.path}: {exc}") from exc
        if len({account.id for account in staff}) != len(staff):
            raise StaffDataError(f"Duplicate staff ID in {self.path}")
        # One account per email, compared case-insensitively, so sign-in never depends
        # on which of two matching records appears first.
        if len({account.email.casefold() for account in staff}) != len(staff):
            raise StaffDataError(f"Duplicate staff email in {self.path}")
        return staff

    def get_staff(self, staff_id: str) -> StaffAccount | None:
        return next((account for account in self.load_staff() if account.id == staff_id), None)

    def find_by_email(self, email: str) -> StaffAccount | None:
        wanted = email.strip().casefold()
        return next((a for a in self.load_staff() if a.email.casefold() == wanted), None)

    def emails(self) -> set[str]:
        return {account.email.casefold() for account in self.load_staff()}

    def add_staff(self, account: StaffAccount, reserved_emails: Callable[[], set[str]]) -> None:
        """Add an account; `reserved_emails` returns customers' casefolded emails.

        Holds the same cross-process lock as customer registration, so the shared email
        rule cannot race even with a running API server.
        """
        with account_email_lock(StaffDataError):
            staff = self.load_staff()
            wanted = account.email.casefold()
            if wanted in reserved_emails() or any(a.email.casefold() == wanted for a in staff):
                raise StaffEmailConflict(account.email)
            if any(a.id == account.id for a in staff):
                raise StaffDataError(f"Duplicate staff ID {account.id}")
            self._save([*staff, account])

    def update_by_email(self, email: str,
                        change: Callable[[StaffAccount | None], StaffAccount]) -> StaffAccount:
        """Read the latest record, apply `change` and save it, all under the account lock.

        `change` receives the stored account (or None) and returns the account to keep;
        it may raise to save nothing. Two processes editing one account therefore each
        build on the other's saved result instead of overwriting it.
        """
        with account_email_lock(StaffDataError):
            staff = self.load_staff()
            wanted = email.strip().casefold()
            index = next((i for i, a in enumerate(staff) if a.email.casefold() == wanted), None)
            current = None if index is None else staff[index]
            updated = change(current)
            if updated is not current:
                if current is None or updated.id != current.id:
                    raise StaffDataError("A staff update must keep the stored account's ID")
                staff[index] = StaffAccount.model_validate(updated.model_dump())
                self._save(staff)
            return updated

    def _save(self, staff: list[StaffAccount]) -> None:
        write_json_array(self.path, [a.model_dump(mode="json") for a in staff], StaffDataError)


class StaffEmailConflict(Exception):
    """Another customer or staff account already uses this email, ignoring case."""
