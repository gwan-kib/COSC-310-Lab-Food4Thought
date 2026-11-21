"""Check Food4Thought's staff provisioning command and service (#107).
Restaurant users and administrators are created locally with a hidden password
prompt, may only manage restaurants that exist, share the email namespace with
customers, and can sign in through POST /auth/login once created.
"""

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scripts.create_staff_account import main
from app.services.staff import (
    InvalidStaffRequestError, StaffEmailTakenError, StaffNotFoundError, StaffProvisioningService,
    UnknownRestaurantError,
)

PASSWORD = "manager-secret-pw"


def _prompt(*answers):
    replies = iter(answers or (PASSWORD, PASSWORD))
    return lambda _label: next(replies)


def _staff(paths):
    return json.loads(paths["staff"].read_text(encoding="utf-8"))


def _all(paths):
    return {name: paths[name].read_bytes() for name in ("staff", "customers", "restaurants")}


def test_command_creates_a_restaurant_manager_that_can_sign_in(m2_store_paths, capsys):
    code = main(["create", "--name", "Cedar Manager", "--email", "Manager@Cedar.invalid",
                 "--role", "restaurant_user", "--restaurant", "restaurant-001"],
                password_prompt=_prompt())

    assert code == 0
    [record] = _staff(m2_store_paths)
    assert (record["email"], record["role"], record["restaurant_ids"]) == (
        "Manager@Cedar.invalid", "restaurant_user", ["restaurant-001"])
    assert record["password_hash"].startswith("$argon2id$")
    output = capsys.readouterr()
    assert PASSWORD not in output.out + output.err
    assert PASSWORD not in m2_store_paths["staff"].read_text()
    login = TestClient(app).post("/auth/login", json={"email": "manager@cedar.invalid", "password": PASSWORD})
    assert (login.status_code, login.json()["role"]) == (200, "restaurant_user")


def test_administrator_is_created_without_restaurants(m2_store_paths):
    assert main(["create", "--name", "Admin", "--email", "admin@food.invalid", "--role", "administrator"],
                password_prompt=_prompt()) == 0
    assert _staff(m2_store_paths)[0]["restaurant_ids"] == []


@pytest.mark.parametrize(("argv", "prompt"), [
    (["--role", "restaurant_user", "--restaurant", "restaurant-404"], None),          # unknown restaurant
    (["--role", "administrator", "--restaurant", "restaurant-001"], None),            # admins own nothing
    (["--role", "restaurant_user"], None),                                            # manager needs one
    (["--role", "restaurant_user", "--restaurant", "restaurant-001"], ("short", "short")),
    (["--role", "restaurant_user", "--restaurant", "restaurant-001"], (PASSWORD, "different-pw-1")),
])
def test_invalid_requests_write_nothing_and_never_print_the_password(m2_store_paths, capsys, argv, prompt):
    before = _all(m2_store_paths)
    code = main(["create", "--name", "X", "--email", "x@food.invalid", *argv],
                password_prompt=_prompt(*(prompt or ())))

    assert code == 1
    assert _all(m2_store_paths) == before
    output = capsys.readouterr()
    assert "Error:" in output.err
    assert PASSWORD not in output.out + output.err


@pytest.mark.parametrize("email", ["ADA@example.invalid", "owner@EXAMPLE.invalid"])
def test_emails_are_unique_across_customers_and_staff(m2_store_paths, auth_accounts, email):
    before = _all(m2_store_paths)
    with pytest.raises(StaffEmailTakenError):
        StaffProvisioningService().create_account(
            name="Dup", email=email, role="restaurant_user", restaurant_ids=["restaurant-001"],
            password=PASSWORD)
    assert _all(m2_store_paths) == before


def test_assign_gives_an_existing_manager_another_restaurant(m2_store_paths, auth_accounts):
    assert main(["assign", "--email", "OWNER@example.invalid", "--restaurant", "restaurant-002"]) == 0
    owner = next(r for r in _staff(m2_store_paths) if r["id"] == "staff-001")
    assert owner["restaurant_ids"] == ["restaurant-001", "restaurant-002"]
    # Assigning the same restaurant again changes nothing.
    before = _all(m2_store_paths)
    assert main(["assign", "--email", "owner@example.invalid", "--restaurant", "restaurant-002"]) == 0
    assert _all(m2_store_paths) == before


@pytest.mark.parametrize(("email", "restaurant", "error"), [
    ("nobody@example.invalid", "restaurant-002", StaffNotFoundError),
    ("admin@example.invalid", "restaurant-002", InvalidStaffRequestError),   # administrators own nothing
    ("owner@example.invalid", "restaurant-404", UnknownRestaurantError),
])
def test_invalid_assignments_write_nothing(m2_store_paths, auth_accounts, email, restaurant, error):
    before = _all(m2_store_paths)
    with pytest.raises(error):
        StaffProvisioningService().assign_restaurant(email=email, restaurant_id=restaurant)
    assert _all(m2_store_paths) == before


# --- PR #117 review: other processes (gwan-kib) ---------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _other_process_holding_the_lock(tmp_path, action, argument):
    """Run tests/account_lock_holder.py and wait until it holds the account lock."""
    signal = tmp_path / f"lock-held-{action}"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    child = subprocess.Popen([sys.executable, str(REPO_ROOT / "tests" / "account_lock_holder.py"),
                              action, str(signal), argument], env=env, cwd=REPO_ROOT)
    try:
        deadline = time.monotonic() + 15
        while not signal.exists():
            assert child.poll() is None, "lock holder exited early"
            assert time.monotonic() < deadline, "lock holder never took the lock"
            time.sleep(0.02)
        yield
    finally:
        assert child.wait(timeout=15) == 0


def test_staff_creation_waits_for_a_registration_in_another_process(m2_store_paths, auth_accounts, tmp_path, capsys):
    # A running API server registers Zed@Example.invalid while the command is creating it.
    before = m2_store_paths["staff"].read_bytes()
    with _other_process_holding_the_lock(tmp_path, "add-customer", "Zed@Example.invalid"):
        code = main(["create", "--name", "Zed", "--email", "zed@example.invalid",
                     "--role", "administrator"], password_prompt=_prompt())

    assert code == 1
    assert "StaffEmailTakenError" in capsys.readouterr().err
    assert m2_store_paths["staff"].read_bytes() == before


def test_concurrent_assignments_keep_every_restaurant(m2_store_paths, auth_accounts, tmp_path):
    restaurants = json.loads(m2_store_paths["restaurants"].read_text(encoding="utf-8"))
    restaurants.append({**restaurants[1], "id": "restaurant-003", "name": "Third Kitchen"})
    m2_store_paths["restaurants"].write_text(json.dumps(restaurants), encoding="utf-8")

    # Another provisioning command adds restaurant-002 while this one adds restaurant-003.
    with _other_process_holding_the_lock(tmp_path, "assign", "owner@example.invalid|restaurant-002"):
        assert main(["assign", "--email", "owner@example.invalid", "--restaurant", "restaurant-003"]) == 0

    [owner] = [a for a in _staff(m2_store_paths) if a["email"] == "owner@example.invalid"]
    assert owner["restaurant_ids"] == ["restaurant-001", "restaurant-002", "restaurant-003"]
