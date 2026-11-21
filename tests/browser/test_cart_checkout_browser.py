"""Exercise Food4Thought's browser cart and checkout against real isolated stores.
Contract-mocked request tests protect the HTTP boundary while end-to-end tests use
real customer sign-in, catalog, cart, checkout and persisted order receipts.
"""

import json
import os

import pytest

if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip("playwright.sync_api", reason="Playwright is not installed")

from playwright.sync_api import expect  # noqa: E402


def sign_in_customer(page, live_server, auth_accounts, key="customer_a"):
    account = auth_accounts.accounts[key]
    page.goto(f"{live_server}/app/account.html")
    page.locator("#signin-form").get_by_label("Email").fill(account.record.email)
    page.locator("#signin-form").get_by_label("Password").fill(account.password)
    page.locator("#signin-form").get_by_role("button", name="Sign in").click()
    expect(page.locator("#profile-email")).to_have_text(account.record.email)
    return account


def add_bowl(page, live_server):
    page.goto(f"{live_server}/app/#/restaurants/restaurant-001")
    expect(page.locator("#menu-list li")).to_have_count(2)
    page.get_by_role("button", name="Add Vegetable bowl to cart").click()
    expect(page.locator("#menu-status")).to_contain_text("Added Vegetable bowl")


def test_mocked_menu_add_sends_authenticated_contract_requests(page, live_server):
    calls = []
    cart = {"id": "cart-1", "customer_id": "customer-001", "revision": 1,
            "restaurant_id": "restaurant-001", "items": [
                {"item_id": "item-001", "name": "Vegetable bowl", "quantity": 1,
                 "unit_price": "12.50", "line_total": "12.50", "available": True}],
            "subtotal": "12.50", "total": "12.50", "checkout_order_id": None}

    def mock_cart(route):
        calls.append((route.request.method, route.request.url,
                      route.request.header_value("authorization"), route.request.post_data_json))
        route.fulfill(status=200, json=cart)

    page.route("**/customers/me/cart", mock_cart)
    page.route("**/customers/me/cart/items", mock_cart)
    page.goto(f"{live_server}/app/")
    page.evaluate("sessionStorage.setItem('food4thought.customer.token', 'mock-customer-token')")
    page.goto(f"{live_server}/app/#/restaurants/restaurant-001")
    expect(page.locator("#menu-list li")).to_have_count(2)
    page.get_by_role("button", name="Add Vegetable bowl to cart").click()
    expect(page.locator("#menu-status")).to_contain_text("Added Vegetable bowl")
    assert [call[0] for call in calls] == ["PUT", "POST"]
    assert all(call[2] == "Bearer mock-customer-token" for call in calls)
    assert calls[1][3] == {"restaurant_id": "restaurant-001", "item_id": "item-001",
                           "quantity": 1}
    assert page.page_errors == []


def test_real_cart_add_quantity_remove_and_clear(page, live_server, auth_accounts, m2_store_paths):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    page.get_by_role("link", name="My cart").click()
    expect(page.locator("#cart-items li")).to_have_count(1)
    expect(page.locator("#cart-total")).to_have_text("$12.50")
    page.get_by_label("Quantity for Vegetable bowl").fill("3")
    page.get_by_role("button", name="Update quantity for Vegetable bowl").click()
    expect(page.locator("#cart-total")).to_have_text("$37.50")
    assert json.loads(m2_store_paths["carts"].read_text())[0]["items"][0]["quantity"] == 3

    page.get_by_role("button", name="Remove Vegetable bowl").click()
    expect(page.locator("#cart-items li")).to_have_count(0)
    expect(page.locator("#cart-total")).to_have_text("$0.00")

    add_bowl(page, live_server)
    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#cart-items li")).to_have_count(1)
    page.get_by_role("button", name="Clear cart").click()
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    saved = json.loads(m2_store_paths["carts"].read_text())[0]
    assert saved["restaurant_id"] is None and saved["items"] == []
    assert page.page_errors == []


def test_real_checkout_persists_order_and_clears_cart(page, live_server, auth_accounts, m2_store_paths):
    account = sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#checkout-button")).to_be_enabled()
    with page.expect_response("**/customers/me/checkout") as response:
        page.locator("#checkout-button").click()
    assert response.value.status == 201
    order = response.value.json()["order"]
    expect(page.locator("#order-confirmation")).to_be_visible()
    expect(page.locator("#order-id")).to_have_text(order["id"])
    expect(page.locator("#order-total")).to_have_text("$12.50")
    expect(page.locator("#cart-total")).to_have_text("$0.00")

    stored = json.loads(m2_store_paths["orders"].read_text())
    assert len(stored) == 1
    assert stored[0]["id"] == order["id"]
    assert stored[0]["customer_id"] == account.record.id
    assert stored[0]["items"][0]["item_id"] == "item-001"
    assert stored[0]["total"] == "12.50"
    page.reload()
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    assert len(json.loads(m2_store_paths["orders"].read_text())) == 1
    assert page.page_errors == []


def test_checkout_rejection_preserves_cart_and_unavailable_item_can_be_removed(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    restaurants = json.loads(m2_store_paths["restaurants"].read_text())
    restaurants[0]["menu_items"][0]["available"] = False
    m2_store_paths["restaurants"].write_text(json.dumps(restaurants), encoding="utf-8")

    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#cart-items")).to_contain_text("Unavailable")
    with page.expect_response("**/customers/me/checkout") as response:
        page.locator("#checkout-button").click()
    assert response.value.status == 409
    expect(page.locator("#cart-error")).to_contain_text("Menu item is unavailable")
    expect(page.locator("#cart-items li")).to_have_count(1)
    assert len(json.loads(m2_store_paths["carts"].read_text())[0]["items"]) == 1
    assert json.loads(m2_store_paths["orders"].read_text()) == []
    page.get_by_role("button", name="Remove Vegetable bowl").click()
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    assert page.page_errors == []


def test_lost_checkout_response_checks_receipt_without_second_post(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    attempts = []

    def lose_checkout_response(route):
        attempts.append(route.request.post_data_json)
        response = route.fetch()
        assert response.status == 201
        route.abort()

    page.route("**/customers/me/checkout", lose_checkout_response)
    page.goto(f"{live_server}/app/cart.html")
    page.locator("#checkout-button").click()
    expect(page.locator("#order-confirmation")).to_be_visible()
    expect(page.locator("#checkout-status")).to_contain_text("saved order")
    page.wait_for_timeout(200)
    assert len(attempts) == 1
    assert len(json.loads(m2_store_paths["orders"].read_text())) == 1
    assert page.page_errors == []


def test_inactive_customer_cannot_change_cart_and_session_errors_are_clear(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    token = page.evaluate("sessionStorage.getItem('food4thought.customer.token')")
    assert page.request.post(f"{live_server}/customers/me/deactivate",
        headers={"Authorization": f"Bearer {token}"}).status == 200
    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#cart-items li")).to_have_count(1)
    page.get_by_role("button", name="Remove Vegetable bowl").click()
    expect(page.locator("#cart-error")).to_contain_text("inactive")
    expect(page.locator("#cart-items li")).to_have_count(1)
    assert page.page_errors == []
