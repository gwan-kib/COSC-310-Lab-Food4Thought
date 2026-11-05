"""Give Food4Thought contract consumers disposable paths for every proposed store.
These fixtures reuse M1's restaurant copy, never touch data/, and can seed the
#78 customer, staff and session stores with isolated authentication accounts.
"""

import pytest

from .auth import AuthFixture, build_auth_fixture

PROPOSED_STORES = ("customers", "carts", "orders", "staff", "sessions")


@pytest.fixture
def m2_store_paths(tmp_path, monkeypatch, isolated_restaurants_path):
    paths = {"restaurants": isolated_restaurants_path}
    for store in PROPOSED_STORES:
        path = tmp_path / f"{store}.json"
        path.write_text("[]\n", encoding="utf-8")
        monkeypatch.setenv(f"{store.upper()}_DATA_PATH", str(path))
        paths[store] = path
    return paths


@pytest.fixture
def auth_accounts(m2_store_paths) -> AuthFixture:
    """Two active customers, a restaurant user, an administrator and their sessions."""
    return build_auth_fixture(m2_store_paths)
