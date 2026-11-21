"""Read Food4Thought's provisioned staff accounts (restaurant users and administrators).
There is no public staff sign-up: #107 provisions these records. This module validates
them strictly so a damaged record is a storage error, never a wrong role.
"""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from app.core.config import get_staff_data_path
from app.core.json_file import read_json_array
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
