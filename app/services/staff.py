"""Provision Food4Thought staff accounts (#107): create restaurant users and
administrators and assign restaurants to managers. Emails are unique across customers
and staff, restaurants must exist, and passwords are stored only as Argon2id hashes.
"""

from typing import Literal
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from app.core.security import hash_password
from app.repositories.customer import CustomerRepository
from app.repositories.restaurant import RestaurantRepository
from app.repositories.staff import StaffAccount, StaffEmailConflict, StaffRepository
from app.schemas.customer import Email, Password, Text  # same rules as customer accounts

_email = TypeAdapter(Email)
_password = TypeAdapter(Password)
_name = TypeAdapter(Text)


class InvalidStaffRequestError(Exception):
    """The request breaks a provisioning rule (bad email or password, wrong restaurants)."""


class StaffEmailTakenError(Exception):
    """Another customer or staff account already uses this email."""


class StaffNotFoundError(Exception):
    """No staff account has this email."""


class UnknownRestaurantError(Exception):
    """A restaurant ID does not exist."""


class StaffProvisioningService:
    def __init__(self, staff: StaffRepository | None = None,
                 customers: CustomerRepository | None = None,
                 restaurants: RestaurantRepository | None = None) -> None:
        self.staff = staff or StaffRepository()
        self.customers = customers or CustomerRepository()
        self.restaurants = restaurants or RestaurantRepository()

    def create_account(self, *, name: str, email: str,
                       role: Literal["restaurant_user", "administrator"],
                       restaurant_ids: list[str], password: str) -> StaffAccount:
        try:
            name, email, password = _name.validate_python(name), _email.validate_python(email), \
                _password.validate_python(password)
        except ValidationError as exc:
            # Report which field failed without echoing any submitted value.
            fields = ", ".join(sorted({str(e["loc"][0]) if e["loc"] else "value" for e in exc.errors()}))
            raise InvalidStaffRequestError(f"Invalid {fields or 'input'}") from None
        if role == "administrator" and restaurant_ids:
            raise InvalidStaffRequestError("Administrators do not manage restaurants")
        if role == "restaurant_user" and not restaurant_ids:
            raise InvalidStaffRequestError("A restaurant user needs at least one --restaurant")
        restaurant_ids = list(dict.fromkeys(restaurant_ids))
        self._require_restaurants(restaurant_ids)
        account = StaffAccount(id=f"staff-{uuid4()}", name=name, email=email, role=role,
                               restaurant_ids=restaurant_ids, password_hash=hash_password(password))
        try:
            self.staff.add_staff(account, reserved_emails=self._customer_emails)
        except StaffEmailConflict:
            raise StaffEmailTakenError(email) from None
        return account

    def assign_restaurant(self, *, email: str, restaurant_id: str) -> StaffAccount:
        def add_restaurant(account: StaffAccount | None) -> StaffAccount:
            # Runs on the latest stored record, under the account lock.
            if account is None:
                raise StaffNotFoundError(email)
            if account.role != "restaurant_user":
                raise InvalidStaffRequestError("Only restaurant users manage restaurants")
            self._require_restaurants([restaurant_id])
            if restaurant_id in account.restaurant_ids:
                return account
            return account.model_copy(update={"restaurant_ids": [*account.restaurant_ids, restaurant_id]})

        return self.staff.update_by_email(email, add_restaurant)

    def _require_restaurants(self, restaurant_ids: list[str]) -> None:
        for restaurant_id in restaurant_ids:
            if self.restaurants.get_record(restaurant_id) is None:
                raise UnknownRestaurantError(restaurant_id)

    def _customer_emails(self) -> set[str]:
        return {customer.email.casefold() for customer in self.customers.load_customers()}
