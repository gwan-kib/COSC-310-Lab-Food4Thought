"""Exercise Food4Thought's customer account API end to end (#79–#82, base of #84).
Registration, sign-in, profile reads and updates run through real routes, services
and isolated JSON stores; the clock is fixed so stored sessions expire predictably.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.main import app
from app.repositories.customer import CustomerRepository
from contracts.auth import FIXED_NOW, SESSION_LIFETIME, token_digest

NEW = {"name": "  Cara Example ", "email": " Cara@Example.invalid ",
       "delivery_address": " 303 Test Lane ", "password": "cara-secret-pw"}


@pytest.fixture
def client(m2_store_paths):
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    yield TestClient(app)
    app.dependency_overrides.pop(get_now, None)


def _customers(paths):
    return json.loads(paths["customers"].read_text(encoding="utf-8"))


def _bytes(paths):
    return {store: paths[store].read_bytes() for store in ("customers", "sessions")}


# --- #79 register -------------------------------------------------------------------

def test_register_creates_one_active_customer_and_returns_only_public_fields(client, m2_store_paths):
    response = client.post("/customers", json=NEW)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "email", "delivery_address", "status"}
    assert (body["name"], body["email"], body["delivery_address"], body["status"]) == (
        "Cara Example", "Cara@Example.invalid", "303 Test Lane", "active")
    [stored] = _customers(m2_store_paths)
    assert stored["id"] == body["id"] and stored["role"] == "customer"
    assert stored["password_hash"].startswith("$argon2id$")
    assert NEW["password"] not in m2_store_paths["customers"].read_text()
    assert CustomerRepository().get_customer(body["id"]).email == "Cara@Example.invalid"


def test_register_rejects_a_duplicate_email_case_insensitively(client, m2_store_paths, auth_accounts):
    before = _bytes(m2_store_paths)
    response = client.post("/customers", json={**NEW, "email": "BEN.EXAMPLE@example.invalid"})

    assert (response.status_code, response.json()) == (409, {"detail": "Email is already registered"})
    assert _bytes(m2_store_paths) == before


@pytest.mark.parametrize("change", [
    {"email": "no-at-sign"}, {"email": "a@"}, {"email": "@b"}, {"email": "a b@c.d"},
    {"name": "   "}, {"delivery_address": ""}, {"password": "short"}, {"password": "x" * 129},
    {"role": "administrator"}, {"status": "inactive"}, {"id": "customer-777"},
    {"name": None}, {"password": 12345678},
])
def test_invalid_registration_creates_nothing_and_never_echoes_the_password(client, m2_store_paths, change):
    response = client.post("/customers", json={**NEW, **change})

    assert response.status_code == 422
    assert NEW["password"] not in response.text
    assert _customers(m2_store_paths) == []


def test_register_save_failure_is_a_generic_500_and_keeps_existing_records(client, m2_store_paths, auth_accounts, monkeypatch):
    before = _bytes(m2_store_paths)
    monkeypatch.setattr("app.core.json_file.os.replace",
                        lambda *_: (_ for _ in ()).throw(OSError("disk full")))

    response = client.post("/customers", json=NEW)

    assert (response.status_code, response.json()) == (500, {"detail": "Customer data is unavailable"})
    assert _bytes(m2_store_paths) == before


# --- #80 sign in ----------------------------------------------------------------------

def test_login_returns_a_bearer_token_that_identifies_the_customer(client, m2_store_paths):
    registered = client.post("/customers", json=NEW).json()

    response = client.post("/auth/login", json={"email": "cara@example.INVALID", "password": NEW["password"]})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "role"}
    assert (body["token_type"], body["role"]) == ("bearer", "customer")
    stored = m2_store_paths["sessions"].read_text()
    assert body["access_token"] not in stored and token_digest(body["access_token"]) in stored
    me = client.get("/customers/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == registered


@pytest.mark.parametrize("credentials", [
    {"email": "ada@example.invalid", "password": "wrong-password-1"},
    {"email": "nobody@example.invalid", "password": "ada-fixture-password-1"},
])
def test_wrong_password_and_unknown_email_get_the_same_401(client, m2_store_paths, auth_accounts, credentials):
    before = _bytes(m2_store_paths)
    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert _bytes(m2_store_paths) == before


@pytest.mark.parametrize("header", [None, "Token abc", "Bearer", "Bearer unknown-token"])
def test_missing_or_invalid_authentication_is_401(client, auth_accounts, header):
    headers = {} if header is None else {"Authorization": header}
    response = client.get("/customers/me", headers=headers)

    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_session_is_401(client, auth_accounts):
    response = client.get("/customers/me",
                          headers={"Authorization": f"Bearer {auth_accounts.expired_token}"})
    assert response.status_code == 401


def test_session_stops_working_once_it_expires(client, auth_accounts):
    headers = auth_accounts.headers("customer_a")
    assert client.get("/customers/me", headers=headers).status_code == 200
    app.dependency_overrides[get_now] = lambda: FIXED_NOW + SESSION_LIFETIME
    assert client.get("/customers/me", headers=headers).status_code == 401


def test_corrupt_session_store_is_500_not_401(client, m2_store_paths, auth_accounts):
    m2_store_paths["sessions"].write_text("{broken", encoding="utf-8")
    response = client.get("/customers/me", headers=auth_accounts.headers("customer_a"))
    assert (response.status_code, response.json()) == (500, {"detail": "Authentication data is unavailable"})


def test_inactive_customer_can_still_sign_in(client, m2_store_paths, auth_accounts):
    records = _customers(m2_store_paths)
    records[0]["status"] = "inactive"
    m2_store_paths["customers"].write_text(json.dumps(records), encoding="utf-8")

    response = client.post("/auth/login", json={"email": "ada@example.invalid",
                                                 "password": "ada-fixture-password-1"})
    assert response.status_code == 200


# --- #81 view profile -------------------------------------------------------------------

def test_customer_reads_their_own_profile_without_writes(client, m2_store_paths, auth_accounts):
    before = _bytes(m2_store_paths)
    response = client.get("/customers/me", headers=auth_accounts.headers("customer_b"))

    assert response.status_code == 200
    assert response.json() == {"id": "customer-002", "name": "Ben Example",
                               "email": "Ben.Example@Example.invalid",
                               "delivery_address": "202 Sample Road, Kelowna, BC", "status": "active"}
    assert _bytes(m2_store_paths) == before


def test_staff_tokens_cannot_use_customer_profile_routes(client, auth_accounts):
    for key in ("restaurant_user", "administrator"):
        response = client.get("/customers/me", headers=auth_accounts.headers(key))
        assert (response.status_code, response.json()) == (403, {"detail": "Operation not permitted"})


def test_token_for_a_deleted_customer_record_is_401(client, m2_store_paths, auth_accounts):
    m2_store_paths["customers"].write_text("[]", encoding="utf-8")
    response = client.get("/customers/me", headers=auth_accounts.headers("customer_a"))
    assert response.status_code == 401


# --- #82 update profile -------------------------------------------------------------------

def test_customer_updates_name_and_address_and_it_persists(client, m2_store_paths, auth_accounts):
    headers = auth_accounts.headers("customer_a")
    response = client.patch("/customers/me", headers=headers,
                            json={"delivery_address": "  9 New Street  "})

    assert response.status_code == 200
    assert response.json()["delivery_address"] == "9 New Street"
    assert response.json()["name"] == "Ada Example"
    stored = {record["id"]: record for record in _customers(m2_store_paths)}
    assert stored["customer-001"]["delivery_address"] == "9 New Street"
    assert stored["customer-001"]["password_hash"] == auth_accounts.accounts["customer_a"].record.password_hash
    assert stored["customer-002"]["delivery_address"] == "202 Sample Road, Kelowna, BC"
    assert client.get("/customers/me", headers=headers).json() == response.json()


@pytest.mark.parametrize("body", [
    {}, {"name": None}, {"delivery_address": "  "}, {"email": "new@example.invalid"},
    {"id": "customer-999"}, {"status": "inactive"}, {"role": "administrator"},
    {"password": "new-password-1"},
])
def test_invalid_or_disallowed_profile_changes_leave_the_record_unchanged(client, m2_store_paths, auth_accounts, body):
    before = _bytes(m2_store_paths)
    response = client.patch("/customers/me", headers=auth_accounts.headers("customer_a"), json=body)

    assert response.status_code == 422
    assert "new-password-1" not in response.text
    assert _bytes(m2_store_paths) == before


def test_inactive_customer_cannot_update_even_with_an_invalid_body(client, m2_store_paths, auth_accounts):
    records = _customers(m2_store_paths)
    records[0]["status"] = "inactive"
    m2_store_paths["customers"].write_text(json.dumps(records), encoding="utf-8")
    before = _bytes(m2_store_paths)
    headers = auth_accounts.headers("customer_a")

    for body in ({"name": "Changed"}, {"name": None}):
        response = client.patch("/customers/me", headers=headers, json=body)
        assert (response.status_code, response.json()) == (403, {"detail": "Customer is inactive"})
    assert _bytes(m2_store_paths) == before
    assert client.get("/customers/me", headers=headers).status_code == 200


def test_unauthenticated_update_is_401_even_with_an_invalid_body(client, m2_store_paths, auth_accounts):
    before = _bytes(m2_store_paths)
    response = client.patch("/customers/me", json={"name": None})
    assert response.status_code == 401
    assert _bytes(m2_store_paths) == before


def test_update_save_failure_is_500_without_partial_changes(client, m2_store_paths, auth_accounts, monkeypatch):
    before = _bytes(m2_store_paths)
    monkeypatch.setattr("app.core.json_file.os.replace",
                        lambda *_: (_ for _ in ()).throw(OSError("disk full")))

    response = client.patch("/customers/me", headers=auth_accounts.headers("customer_a"),
                            json={"name": "Changed"})

    assert (response.status_code, response.json()) == (500, {"detail": "Customer data is unavailable"})
    assert _bytes(m2_store_paths) == before
