"""Isolate restaurant and all M2 store paths for every test.
Customer, cart, staff and session stores start empty; order storage stays absent
until a test explicitly requests initialized M2 stores. The session guard
detects unexpected writes to committed application data.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

# tests/ has no __init__.py, so pytest puts it on sys.path for this conftest.
from contracts.auth import AuthFixture, build_auth_fixture

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _snapshot_data_files() -> dict[str, str]:
    return {
        str(path.relative_to(DATA_DIR)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(DATA_DIR.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="session", autouse=True)
def committed_data_is_unchanged():
    before = _snapshot_data_files()
    yield
    after = _snapshot_data_files()
    assert after == before, "Tests changed files under data/"


@pytest.fixture(autouse=True)
def isolated_restaurants_path(tmp_path, monkeypatch) -> Path:
    """Point the app at a per-test copy of the representative restaurant data."""
    path = tmp_path / "restaurants.json"
    shutil.copyfile(DATA_DIR / "restaurants.json", path)
    monkeypatch.setenv("RESTAURANTS_DATA_PATH", str(path))
    return path


# Select a disposable path even in tests that do not initialize order storage.
@pytest.fixture(autouse=True)
def isolated_orders_path(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "orders.json"
    monkeypatch.setenv("ORDERS_DATA_PATH", str(path))
    return path


# Additional stores proposed by the M2 and authentication contracts.
ADDITIONAL_M2_STORES = ("customers", "carts", "staff", "sessions")


@pytest.fixture(autouse=True)
def isolated_additional_m2_stores(tmp_path, monkeypatch, isolated_orders_path) -> dict[str, Path]:
    """Set up the other M2 stores for every test, but leave orders.json absent."""
    paths = {"orders": isolated_orders_path}
    for store in ADDITIONAL_M2_STORES:
        path = tmp_path / f"{store}.json"
        path.write_text("[]\n", encoding="utf-8")
        monkeypatch.setenv(f"{store.upper()}_DATA_PATH", str(path))
        paths[store] = path
    return paths


@pytest.fixture
def m2_store_paths(isolated_restaurants_path, isolated_additional_m2_stores) -> dict[str, Path]:
    """Return all temporary paths and initialize orders only when requested."""
    paths = {"restaurants": isolated_restaurants_path, **isolated_additional_m2_stores}
    paths["orders"].write_text("[]\n", encoding="utf-8")
    return paths


@pytest.fixture
def auth_accounts(m2_store_paths) -> AuthFixture:
    """Two active customers, a restaurant user, an administrator and their sessions."""
    return build_auth_fixture(m2_store_paths)

@pytest.fixture
def menu_manager(auth_accounts, monkeypatch):
    """Allow the fixture manager to edit the synthetic target restaurant in M1 tests."""
    from app.api.auth import get_now
    from app.main import app
    from app.schemas.customer import Principal

    path = auth_accounts.paths["staff"]
    staff = json.loads(path.read_bytes())
    owner = next(account for account in staff if account["role"] == "restaurant_user")
    owner["restaurant_ids"].extend(["target", "legacy", "restaurant-002"])
    path.write_text(json.dumps(staff), encoding="utf-8")
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    return Principal(account_id=owner["id"], role=owner["role"])


@pytest.fixture
def manager_client(menu_manager, auth_accounts):
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app, headers=auth_accounts.headers("restaurant_user"),
                      raise_server_exceptions=False)

@pytest.fixture
def admin_client(auth_accounts, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.auth import get_now
    from app.main import app

    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    return TestClient(app, headers=auth_accounts.headers("administrator"),
                      raise_server_exceptions=False)
