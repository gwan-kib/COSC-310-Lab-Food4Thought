"""Prove Food4Thought's #78 authentication fixtures reach tests outside tests/contracts.
API, service and browser tests for #79–#84 and #94 share these accounts and stores.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_api_tests_receive_isolated_stores_and_accounts(m2_store_paths, auth_accounts, tmp_path):
    assert auth_accounts.paths is m2_store_paths
    assert {"customers", "carts", "orders", "staff", "sessions"} <= set(m2_store_paths)
    assert all(path.parent == tmp_path for path in m2_store_paths.values())
    assert {"customer_a", "customer_b", "restaurant_user", "administrator"} == set(
        auth_accounts.accounts
    )


def test_restaurant_manager_fixture_matches_the_running_app(auth_accounts):
    # The app reads the same isolated restaurant copy that the fixture assigned.
    [managed_id] = auth_accounts.accounts["restaurant_user"].record.restaurant_ids
    response = TestClient(app).get(f"/restaurants/{managed_id}")

    assert response.status_code == 200
    assert response.json()["id"] == managed_id
