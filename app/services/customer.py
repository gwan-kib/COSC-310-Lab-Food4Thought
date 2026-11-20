"""Apply Food4Thought's customer account rules: register (#79), read (#81), update
(#82) and deactivate (#83) a profile. Emails are unique ignoring case, passwords are hashed before storage,
and profile changes re-check that the customer is still active under the workflow lock.
"""

from uuid import uuid4

from app.core.security import hash_password
from app.core.workflow import workflow_lock
from app.repositories.customer import CustomerRepository, DuplicateEmailError
from app.schemas.customer import Customer, CustomerProfileUpdate, CustomerRegistration, StoredCustomer


class CustomerNotFoundError(Exception):
    """No customer record exists for the authenticated identity."""


class CustomerInactiveError(Exception):
    """A deactivated customer cannot change their profile."""


__all__ = ["CustomerService", "CustomerNotFoundError", "CustomerInactiveError", "DuplicateEmailError"]


class CustomerService:
    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    def register(self, request: CustomerRegistration) -> Customer:
        if self.repository.find_by_email(request.email) is not None:
            raise DuplicateEmailError(request.email)
        existing_ids = {customer.id for customer in self.repository.load_customers()}
        customer_id = str(uuid4())
        while customer_id in existing_ids:
            customer_id = str(uuid4())
        customer = StoredCustomer(
            id=customer_id, name=request.name, email=request.email,
            delivery_address=request.delivery_address, status="active",
            role="customer", password_hash=hash_password(request.password),
        )
        self.repository.add_customer(customer)  # returns only after the save succeeds
        return customer.public()

    def get_profile(self, customer_id: str) -> Customer:
        customer = self.repository.get_customer(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer.public()

    def update_profile(self, customer_id: str, request: CustomerProfileUpdate) -> Customer:
        with workflow_lock:
            customer = self.repository.get_customer(customer_id)
            if customer is None:
                raise CustomerNotFoundError(customer_id)
            if customer.status != "active":
                raise CustomerInactiveError(customer_id)
            # Only fields the client actually sent change; ID, email, role and hash are kept.
            updated = customer.model_copy(update=request.model_dump(exclude_unset=True))
            updated = StoredCustomer.model_validate(updated.model_dump())
            self.repository.save_customer(updated)
            return updated.public()

    def deactivate(self, customer_id: str) -> Customer:
        """Mark the account inactive, keeping its ID, cart and orders; repeating is a no-op."""
        # Same lock as cart edits and checkout, so a racing checkout sees the result.
        with workflow_lock:
            customer = self.repository.get_customer(customer_id)
            if customer is None:
                raise CustomerNotFoundError(customer_id)
            if customer.status == "inactive":
                return customer.public()
            updated = customer.model_copy(update={"status": "inactive"})
            self.repository.save_customer(updated)
            return updated.public()
