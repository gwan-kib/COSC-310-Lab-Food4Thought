"""Give each Food4Thought test disposable restaurant and M2 store paths.
A session-level snapshot detects changes under data/, and tests needing seeded
accounts can request the shared authentication fixture.
"""

import hashlib
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


# Stores proposed by the M2 contract (#77) and the authentication design (#78).
M2_STORES = ("customers", "carts", "orders", "staff", "sessions")


@pytest.fixture(autouse=True)
def m2_store_paths(tmp_path, monkeypatch, isolated_restaurants_path) -> dict[str, Path]:
    """Empty, isolated JSON stores, each selected through its *_DATA_PATH variable."""
    paths = {"restaurants": isolated_restaurants_path}
    for store in M2_STORES:
        path = tmp_path / f"{store}.json"
        path.write_text("[]\n", encoding="utf-8")
        monkeypatch.setenv(f"{store.upper()}_DATA_PATH", str(path))
        paths[store] = path
    return paths


@pytest.fixture
def auth_accounts(m2_store_paths) -> AuthFixture:
    """Two active customers, a restaurant user, an administrator and their sessions."""
    return build_auth_fixture(m2_store_paths)
