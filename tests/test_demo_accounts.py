"""Exercise Food4Thought's optional demo setup using isolated stores and real sign-in.
Check that it seeds all roles once and keeps existing demo data across launches.
"""

import json

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import app
from app.scripts.run_demo import create_demo_app


def test_demo_accounts_are_available_only_on_demo_server(tmp_path):
    directory = tmp_path / "demo"
    assert TestClient(app).get("/demo-accounts").status_code == 404

    demo = create_demo_app(directory)
    assert TestClient(demo, base_url="http://unexpected.invalid").get("/demo-accounts").status_code == 400

    client = TestClient(demo, base_url="http://127.0.0.1")
    response = client.get("/demo-accounts")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "/demo-accounts" not in client.get("/openapi.json").json()["paths"]
    accounts = response.json()
    assert set(accounts) == {"customer", "restaurant_user", "administrator"}
    restarted = TestClient(create_demo_app(directory), base_url="http://127.0.0.1")
    assert restarted.get("/demo-accounts").json() == accounts

    headers = {}
    for role, account in accounts.items():
        credentials = {key: account[key] for key in ("email", "password")}
        login = restarted.post("/auth/login", json=credentials)
        assert login.status_code == 200
        assert login.json()["role"] == role
        headers[role] = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert restarted.get("/customers/me", headers=headers["customer"]).status_code == 200
    assert restarted.get("/customers/me", headers=headers["administrator"]).status_code == 403
    restaurant = {"name": "Demo Test Cafe", "cuisine": "Cafe", "description": "Demo cafe"}
    assert restarted.post("/restaurants", headers=headers["restaurant_user"], json=restaurant).status_code == 403
    assert restarted.post("/restaurants", headers=headers["administrator"], json=restaurant).status_code == 201
    rename = {"name": "Demo Cedar Bowl"}
    assert restarted.patch("/restaurants/restaurant-001", headers=headers["restaurant_user"], json=rename).status_code == 200
    assert restarted.patch("/restaurants/restaurant-002", headers=headers["restaurant_user"], json=rename).status_code == 403
    manager = next(account for account in json.loads((directory / "staff.json").read_text())
                   if account["role"] == "restaurant_user")
    assert manager["restaurant_ids"] == [accounts["restaurant_user"]["restaurant_id"]] == ["restaurant-001"]


def test_repeat_setup_preserves_changes_and_creates_missing_account(tmp_path):
    directory = tmp_path / "demo"
    create_demo_app(directory)
    customers = directory / "customers.json"
    customer = json.loads(customers.read_text())[0]
    customer["name"] = "Edited Demo Name"
    customer["password_hash"] = hash_password("different-test-password")
    customers.write_text(json.dumps([customer]), encoding="utf-8")

    staff_path = directory / "staff.json"
    manager = next(account for account in json.loads(staff_path.read_text())
                   if account["role"] == "restaurant_user")
    staff_path.write_text(json.dumps([manager]), encoding="utf-8")
    cart_path, orders_path = directory / "carts.json", directory / "orders.json"
    for path in (cart_path, orders_path):
        path.write_bytes(b"[ ]\n")

    create_demo_app(directory)

    assert json.loads(customers.read_text()) == [customer]
    staff = json.loads(staff_path.read_text())
    assert len(staff) == 2
    assert manager in staff
    assert cart_path.read_bytes() == orders_path.read_bytes() == b"[ ]\n"
