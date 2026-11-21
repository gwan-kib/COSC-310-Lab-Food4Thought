# Coordinate Food4Thought's restaurant filtering, resource lookups, and management
# operations without depending on HTTP. Apply changes to current records through
# repository mutation callbacks, keeping generated IDs and menu-item lookups scoped
# to the appropriate resource.

from uuid import uuid4

from app.core.workflow import workflow_lock
from app.repositories.staff import StaffAccount, StaffRepository
from app.schemas.customer import Principal
from app.repositories.restaurant import RestaurantRepository
from app.schemas.restaurant import (
    Menu,
    MenuItem,
    MenuItemCreate,
    MenuItemUpdate,
    Restaurant,
    RestaurantCreate,
    RestaurantRecord,
    RestaurantUpdate,
)


class RestaurantNotFoundError(Exception):
    """No restaurant exists with the requested identifier."""


class MenuItemNotFoundError(Exception):
    """No item exists with the requested identifier under this restaurant."""


class AuthenticationRequired(Exception):
    """The caller has no current authenticated account."""


class PermissionDenied(Exception):
    """The caller lacks the required role or restaurant assignment."""


class RestaurantService:
    """Provide restaurant discovery and management through the repository boundary."""

    def __init__(
        self, repository: RestaurantRepository, *,
        principal: Principal | None = None, staff: StaffRepository | None = None,
    ) -> None:
        self.repository = repository
        self.principal = principal
        self.staff = staff if staff is not None else StaffRepository()

    def _require_staff(self, role: str) -> StaffAccount:
        if self.principal is None:
            raise AuthenticationRequired()
        if self.principal.role != role:
            raise PermissionDenied()
        account = self.staff.get_staff(self.principal.account_id)
        if account is None:
            raise AuthenticationRequired()
        if account.role != role:
            raise PermissionDenied()
        return account

    @staticmethod
    def _require_assignment(account: StaffAccount, restaurant_id: str) -> None:
        if restaurant_id not in account.restaurant_ids:
            raise PermissionDenied()

    def list_restaurants(self, cuisine: str | None = None) -> list[Restaurant]:
        """Return restaurants in stored order, optionally only one cuisine.

        Matching compares the whole value case-insensitively; casefold() also
        handles letters such as "ß" that lower() leaves unchanged.
        """
        restaurants = self.repository.list_restaurants()
        if cuisine is None:
            return restaurants
        wanted = cuisine.strip().casefold()
        return [r for r in restaurants if r.cuisine.casefold() == wanted]

    def get_restaurant(self, restaurant_id: str) -> Restaurant:
        record = self.repository.get_record(restaurant_id)
        if record is None:
            raise RestaurantNotFoundError(restaurant_id)
        return record.as_restaurant()

    def get_menu(self, restaurant_id: str) -> Menu:
        # The repository only reports absence; treating it as an error is an
        # application decision, so it is made here rather than in storage.
        record = self.repository.get_record(restaurant_id)
        if record is None:
            raise RestaurantNotFoundError(restaurant_id)
        return Menu(restaurant_id=record.id, items=record.menu_items)

    def create_restaurant(self, request: RestaurantCreate) -> Restaurant:
        self._require_staff("administrator")

        def add(records: list[RestaurantRecord]) -> None:
            existing_ids = {record.id for record in records}
            identifier = str(uuid4())
            while identifier in existing_ids:
                identifier = str(uuid4())

            record = RestaurantRecord(
                id=identifier, **request.model_dump(), menu_items=[]
            )
            records.append(record)

        return self.repository.mutate_records(add)[-1].as_restaurant()

    def update_restaurant(
        self, restaurant_id: str, request: RestaurantUpdate
    ) -> Restaurant:
        manager = self._require_staff("restaurant_user")
        changes = request.model_dump(exclude_unset=True)

        def update(records: list[RestaurantRecord]) -> None:
            # Look up current state inside the mutation lock, never a stale snapshot.
            for record in records:
                if record.id == restaurant_id:
                    self._require_assignment(manager, restaurant_id)
                    for field, value in changes.items():
                        setattr(record, field, value)
                    return
            raise RestaurantNotFoundError(restaurant_id)

        saved = self.repository.mutate_records(update)
        return next(record for record in saved if record.id == restaurant_id).as_restaurant()

    def add_menu_item(self, restaurant_id: str, request: MenuItemCreate) -> MenuItem:
        """Append an item to an existing restaurant and return its persisted form."""
        created_id: str | None = None

        def add(records: list[RestaurantRecord]) -> None:
            nonlocal created_id
            # Check the current parent and IDs inside the locked mutation.
            record = next((r for r in records if r.id == restaurant_id), None)
            if record is None:
                raise RestaurantNotFoundError(restaurant_id)
            self._require_assignment(manager, restaurant_id)

            existing_ids = {item.id for item in record.menu_items}
            identifier = str(uuid4())
            while identifier in existing_ids:
                identifier = str(uuid4())
            created_id = identifier
            record.menu_items.append(MenuItem(id=identifier, **request.model_dump()))

        with workflow_lock:
            manager = self._require_staff("restaurant_user")
            saved = self.repository.mutate_records(add)
        parent = next(record for record in saved if record.id == restaurant_id)
        return next(item for item in parent.menu_items if item.id == created_id)

    def update_menu_item(
        self, restaurant_id: str, item_id: str, request: MenuItemUpdate
    ) -> MenuItem:
        changes = request.model_dump(exclude_unset=True)

        def update(records: list[RestaurantRecord]) -> None:
            # Resolve both IDs against current state inside the shared mutation lock.
            parent = next((r for r in records if r.id == restaurant_id), None)
            if parent is None:
                raise RestaurantNotFoundError(restaurant_id)
            self._require_assignment(manager, restaurant_id)
            item = next((i for i in parent.menu_items if i.id == item_id), None)
            if item is None:
                raise MenuItemNotFoundError(item_id)
            for field, value in changes.items():
                setattr(item, field, value)

        with workflow_lock:
            manager = self._require_staff("restaurant_user")
            saved = self.repository.mutate_records(update)
        parent = next(record for record in saved if record.id == restaurant_id)
        return next(item for item in parent.menu_items if item.id == item_id)
