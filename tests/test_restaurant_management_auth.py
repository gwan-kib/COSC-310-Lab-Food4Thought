"""Check administrator creation and manager edits through HTTP and the service.
Every denied write must leave the complete restaurant store untouched.
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.main import app
from app.repositories.restaurant import RestaurantRepository
from app.repositories.staff import StaffRepository
from app.schemas.customer import Principal
from app.schemas.restaurant import RestaurantCreate, RestaurantUpdate
from app.services.restaurant import AuthenticationRequired, PermissionDenied, RestaurantService

CREATE = {"name": "Cafe", "description": "Lunch", "cuisine": "Fusion"}
EDIT = {"name": "Changed"}


@pytest.mark.parametrize(("role", "method", "target", "body", "status"), [
    (None, "POST", "/restaurants", CREATE, 401),
    (None, "PATCH", "/restaurants/restaurant-001", EDIT, 401),
    ("customer_a", "POST", "/restaurants", CREATE, 403),
    ("customer_a", "PATCH", "/restaurants/restaurant-001", EDIT, 403),
    ("restaurant_user", "POST", "/restaurants", CREATE, 403),
    ("administrator", "PATCH", "/restaurants/restaurant-001", EDIT, 403),
    ("restaurant_user", "PATCH", "/restaurants/restaurant-002", EDIT, 403),
    ("restaurant_user", "PATCH", "/restaurants/missing", EDIT, 404),
    ("administrator", "PATCH", "/restaurants/missing", {}, 403),
    ("restaurant_user", "PATCH", "/restaurants/missing", {}, 422),
    (None, "POST", "/restaurants", {}, 401),
    ("administrator", "POST", "/restaurants", CREATE, 201),
    ("restaurant_user", "PATCH", "/restaurants/restaurant-001", EDIT, 200),
])
def test_management_write_policy(auth_accounts, monkeypatch, role, method, target, body, status):
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    path = auth_accounts.paths["restaurants"]
    before = path.read_bytes()
    headers = auth_accounts.headers(role) if role else {}
    result = TestClient(app).request(method, target, headers=headers, json=body)
    assert result.status_code == status
    if status == 401:
        assert result.headers["www-authenticate"] == "Bearer"
    if status >= 400:
        assert path.read_bytes() == before
    else:
        saved = RestaurantRepository(path).get_record(result.json()["id"])
        assert saved.name == body["name"]


@pytest.mark.parametrize(("role", "operation", "expected"), [
    (None, "create", AuthenticationRequired),
    (None, "update", AuthenticationRequired),
    ("customer", "update", PermissionDenied),
    ("restaurant_user", "create", PermissionDenied),
    ("administrator", "update", PermissionDenied),
    ("restaurant_user", "update", PermissionDenied),
    ("administrator", "create", None),
    ("restaurant_user", "assigned", None),
])
def test_service_checks_injected_staff(isolated_restaurants_path, role, operation, expected):
    principal = Principal(account_id="staff", role=role) if role else None
    staff = Mock(spec=StaffRepository)
    staff.get_staff.return_value = Mock(role=role, restaurant_ids=["restaurant-001"])
    service = RestaurantService(RestaurantRepository(isolated_restaurants_path),
                                principal=principal, staff=staff)
    before = isolated_restaurants_path.read_bytes()

    def write():
        if operation == "create":
            return service.create_restaurant(RestaurantCreate(**CREATE))
        target = "restaurant-001" if operation == "assigned" else "restaurant-002"
        return service.update_restaurant(target, RestaurantUpdate(**EDIT))

    if expected:
        with pytest.raises(expected):
            write()
        assert isolated_restaurants_path.read_bytes() == before
    else:
        assert write().name == ("Cafe" if operation == "create" else "Changed")
        staff.get_staff.assert_called_once_with("staff")
