"""Characterize shared authorization/error precedence across M2 write boundaries (#102).

Use the real HTTP app, authentication and disposable JSON stores. These tests
complement feature-level behavior tests: an invalid model cannot expose a
protected route or mutate another subsystem's persisted state.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.main import app


# (HTTP method, route, allowed identity, disallowed identity).
# Each route takes a Pydantic object body; [] is valid JSON but not that object.
PROTECTED_WRITES = (
    ("PATCH", "/customers/me", "customer_a", "restaurant_user"),
    ("POST", "/customers/me/cart/items", "customer_a", "restaurant_user"),
    ("PATCH", "/customers/me/cart/items/item-001", "customer_a", "restaurant_user"),
    ("POST", "/customers/me/checkout", "customer_a", "restaurant_user"),
    ("PATCH", "/restaurants/restaurant-001/menu/items/item-001",
     "restaurant_user", "customer_a"),
)

CUSTOMER_WRITES = PROTECTED_WRITES[:-1]


@pytest.fixture
def client(auth_accounts, monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    with TestClient(app) as http:
        yield http


def _store_snapshot(paths):
    """Include absent files so a denied request cannot silently create storage."""
    return {
        name: path.read_bytes() if path.exists() else None
        for name, path in paths.items()
    }


@pytest.mark.parametrize("method,path,allowed,wrong_role", PROTECTED_WRITES)
def test_auth_and_role_denial_precede_invalid_write_body(
        client, auth_accounts, m2_store_paths, method, path, allowed, wrong_role):
    before = _store_snapshot(m2_store_paths)

    unauthenticated = client.request(method, path, json=[], headers={})
    assert (unauthenticated.status_code, unauthenticated.json()) == (
        401, {"detail": "Authentication required"})
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    assert _store_snapshot(m2_store_paths) == before

    wrong_role_response = client.request(
        method, path, json=[], headers=auth_accounts.headers(wrong_role))
    assert (wrong_role_response.status_code, wrong_role_response.json()) == (
        403, {"detail": "Operation not permitted"})
    assert _store_snapshot(m2_store_paths) == before

    # Proves the body really is invalid, rather than relying on a successful
    # auth denial to hide an accidentally valid request.
    allowed_response = client.request(
        method, path, json=[], headers=auth_accounts.headers(allowed))
    assert allowed_response.status_code == 422
    assert allowed_response.json()["detail"][0]["loc"][0] == "body"
    assert _store_snapshot(m2_store_paths) == before


@pytest.mark.parametrize("method,path,allowed,wrong_role", CUSTOMER_WRITES)
def test_inactive_customer_denial_precedes_invalid_write_body(
        client, auth_accounts, m2_store_paths, method, path, allowed, wrong_role):
    headers = auth_accounts.headers(allowed)
    disabled = client.post("/customers/me/deactivate", headers=headers)
    assert (disabled.status_code, disabled.json()["status"]) == (200, "inactive")
    before = _store_snapshot(m2_store_paths)

    response = client.request(method, path, json=[], headers=headers)
    assert (response.status_code, response.json()) == (
        403, {"detail": "Customer is inactive"})
    assert _store_snapshot(m2_store_paths) == before
