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
    page.get_by_role("spinbutton", name="Quantity for Vegetable bowl").fill("3")
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


def test_mixed_restaurants_show_backend_conflict_without_replacing_cart(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    page.goto(f"{live_server}/app/#/restaurants/restaurant-002")
    expect(page.locator("#menu-list li")).to_have_count(2)
    page.get_by_role("button", name="Add Margherita pizza to cart").click()
    expect(page.locator("#menu-status")).to_contain_text("Cart belongs to another restaurant")
    saved = json.loads(m2_store_paths["carts"].read_text())[0]
    assert saved["restaurant_id"] == "restaurant-001"
    assert saved["items"] == [{"item_id": "item-001", "quantity": 1}]
    assert page.page_errors == []


def test_invalid_cart_quantity_and_api_validation_keep_stored_cart_unchanged(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#cart-items li")).to_have_count(1)
    original = m2_store_paths["carts"].read_bytes()
    page.get_by_role("spinbutton", name="Quantity for Vegetable bowl").fill("0")
    page.locator(".cart-line-controls").evaluate(
        "form => form.dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}))"
    )
    expect(page.locator("#cart-error")).to_contain_text("positive whole number")
    assert m2_store_paths["carts"].read_bytes() == original

    page.route("**/customers/me/cart/items/item-001", lambda route: route.fulfill(
        status=422, json={"detail": [{"loc": ["body", "quantity"], "msg": "Invalid value"}]}
    ))
    page.get_by_role("spinbutton", name="Quantity for Vegetable bowl").fill("2")
    page.get_by_role("button", name="Update quantity for Vegetable bowl").click()
    expect(page.locator("#cart-error")).to_contain_text("Invalid input")
    expect(page.locator("#cart-total")).to_have_text("$12.50")
    assert m2_store_paths["carts"].read_bytes() == original
    assert page.page_errors == []


def test_menu_and_receipt_render_server_text_safely_on_narrow_screen(
    page, live_server, auth_accounts, m2_store_paths
):
    dangerous_name = '<img src=x onerror="window.injected=true"> Bowl'
    records = json.loads(m2_store_paths["restaurants"].read_text())
    records[0]["menu_items"][0]["name"] = dangerous_name
    m2_store_paths["restaurants"].write_text(json.dumps(records), encoding="utf-8")
    page.set_viewport_size({"width": 390, "height": 844})
    sign_in_customer(page, live_server, auth_accounts)
    page.goto(f"{live_server}/app/#/restaurants/restaurant-001")
    expect(page.locator("#menu-list li").first).to_contain_text(dangerous_name)
    page.get_by_role("button", name=f"Add {dangerous_name} to cart").click()
    expect(page.locator("#menu-status")).to_contain_text("Added")
    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#cart-items")).to_contain_text(dangerous_name)
    page.locator("#checkout-button").click()
    expect(page.locator("#order-confirmation")).to_contain_text(dangerous_name)
    assert page.locator("#cart-items img, #order-items img").count() == 0
    assert page.evaluate("window.injected") is None
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.page_errors == []


def test_switching_customer_does_not_trap_new_account_in_old_checkout_attempt(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    first_cart = json.loads(m2_store_paths["carts"].read_text())[0]
    page.evaluate("(cart) => sessionStorage.setItem('food4thought.customer.checkout.attempt',"
                  " JSON.stringify({customer_id: cart.customer_id, cart_id: cart.id,"
                  " cart_revision: cart.revision}))", first_cart)

    other = auth_accounts.accounts["customer_b"]
    logged_in = page.request.post(f"{live_server}/auth/login", data={
        "email": other.record.email, "password": other.password,
    })
    assert logged_in.status == 200
    page.evaluate("(token) => sessionStorage.setItem('food4thought.customer.token', token)",
                  logged_in.json()["access_token"])
    page.goto(f"{live_server}/app/cart.html")
    expect(page.get_by_role("button", name="Create cart")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('food4thought.customer.checkout.attempt')") is None
    page.get_by_role("button", name="Create cart").click()
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    stored = json.loads(m2_store_paths["carts"].read_text())
    assert len(stored) == 2
    assert any(c["customer_id"] == other.record.id and c["items"] == [] for c in stored)
    assert any(c["id"] == first_cart["id"] and c["items"] == first_cart["items"] for c in stored)
    assert page.page_errors == []


def test_pending_checkout_reset_requires_explicit_same_revision_replay(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    calls = []

    def simulate_pending_reset(route):
        calls.append(route.request.post_data_json)
        actual = route.fetch()
        body = actual.json()
        if len(calls) == 1:
            assert actual.status == 201
            body["cart_reset_pending"] = True
            route.fulfill(status=201, json=body)
        else:
            route.fulfill(status=actual.status, json=body)

    page.route("**/customers/me/checkout", simulate_pending_reset)
    page.goto(f"{live_server}/app/cart.html")
    page.locator("#checkout-button").click()
    expect(page.locator("#order-confirmation")).to_be_visible()
    expect(page.get_by_role("button", name="Complete cart reset")).to_be_visible()
    page.wait_for_timeout(250)
    assert len(calls) == 1

    page.get_by_role("button", name="Complete cart reset").click()
    expect(page.locator("#checkout-status")).to_be_hidden()
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    assert len(calls) == 2 and calls[0] == calls[1]
    assert len(json.loads(m2_store_paths["orders"].read_text())) == 1
    assert page.page_errors == []


def test_lost_checkout_response_still_finds_receipt_when_cart_read_fails(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    posts = []
    history_reads = []

    def lost_response(route):
        posts.append(route.request.post_data_json)
        assert route.fetch().status == 201
        route.abort()

    def fail_cart_after_checkout(route):
        if posts:
            route.fulfill(status=500, json={"detail": "Cart data is unavailable"})
        else:
            route.continue_()

    page.route("**/customers/me/checkout", lost_response)
    page.route("**/customers/me/cart", fail_cart_after_checkout)
    page.route("**/customers/me/orders", lambda route: (
        history_reads.append(route.request.method), route.continue_()
    ))
    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#cart-total")).to_have_text("$12.50")
    page.get_by_role("button", name="Place order").click()
    expect(page.locator("#order-confirmation")).to_be_visible()
    saved = json.loads(m2_store_paths["orders"].read_text())
    assert len(saved) == 1
    expect(page.locator("#order-id")).to_have_text(saved[0]["id"])
    expect(page.locator("#checkout-status")).to_contain_text("cannot confirm")
    expect(page.get_by_role("button", name="Retry original checkout")).to_be_hidden()
    assert history_reads == ["GET"]
    assert len(posts) == 1

    page.unroute("**/customers/me/cart", fail_cart_after_checkout)
    page.get_by_role("button", name="Refresh cart").click()
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    expect(page.locator("#checkout-status")).to_contain_text("No checkout retry is needed")
    assert len(posts) == 1
    assert len(json.loads(m2_store_paths["orders"].read_text())) == 1
    assert page.page_errors == []


def test_checkout_revision_conflict_refreshes_changed_total_before_resubmission(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    page.goto(f"{live_server}/app/cart.html")
    expect(page.locator("#cart-total")).to_have_text("$12.50")
    token = page.evaluate("sessionStorage.getItem('food4thought.customer.token')")
    edited = page.request.patch(
        f"{live_server}/customers/me/cart/items/item-001",
        data={"quantity": 2}, headers={"Authorization": f"Bearer {token}"},
    )
    assert edited.status == 200
    assert edited.json()["total"] == "25.00"

    with page.expect_response("**/customers/me/checkout") as first:
        page.get_by_role("button", name="Place order").click()
    assert first.value.status == 409
    expect(page.locator("#cart-total")).to_have_text("$25.00")
    expect(page.get_by_role("spinbutton", name="Quantity for Vegetable bowl")).to_have_value("2")
    expect(page.locator("#cart-status")).to_contain_text("Review the updated cart")
    expect(page.get_by_role("button", name="Place order")).to_be_enabled()
    assert json.loads(m2_store_paths["orders"].read_text()) == []

    with page.expect_response("**/customers/me/checkout") as second:
        page.get_by_role("button", name="Place order").click()
    assert second.value.status == 201
    expect(page.locator("#order-total")).to_have_text("$25.00")
    assert len(json.loads(m2_store_paths["orders"].read_text())) == 1
    assert page.page_errors == []


def test_cart_and_receipt_display_large_integer_quantity_without_rounding(
    page, live_server, auth_accounts, m2_store_paths
):
    sign_in_customer(page, live_server, auth_accounts)
    token = page.evaluate("sessionStorage.getItem('food4thought.customer.token')")
    headers = {"Authorization": f"Bearer {token}"}
    assert page.request.put(f"{live_server}/customers/me/cart", headers=headers).status == 201
    big = 9007199254740993
    added = page.request.post(
        f"{live_server}/customers/me/cart/items",
        data='{"restaurant_id":"restaurant-001","item_id":"item-001","quantity":9007199254740993}',
        headers={**headers, "Content-Type": "application/json"},
    )
    assert added.status == 200
    assert json.loads(m2_store_paths["carts"].read_text())[0]["items"][0]["quantity"] == big

    page.goto(f"{live_server}/app/cart.html")
    expect(page.get_by_role("spinbutton", name="Quantity for Vegetable bowl")).to_have_value(str(big))
    page.get_by_role("button", name="Place order").click()
    expect(page.locator("#order-confirmation")).to_be_visible()
    expect(page.locator("#order-items")).to_contain_text(str(big))
    order = json.loads(m2_store_paths["orders"].read_text())[0]
    assert order["items"][0]["quantity"] == big
    assert page.locator("#order-items").inner_text().count(str(big)) == 1
    assert page.page_errors == []


def test_checkout_validation_does_not_report_quantity_error(page, live_server, auth_accounts):
    sign_in_customer(page, live_server, auth_accounts)
    add_bowl(page, live_server)
    page.route("**/customers/me/checkout", lambda route: route.fulfill(
        status=422, json={"detail": [{"loc": ["body", "cart_id"],
                                       "msg": "Invalid cart ID"}]}
    ))
    page.goto(f"{live_server}/app/cart.html")
    page.get_by_role("button", name="Place order").click()
    expect(page.locator("#cart-error")).to_contain_text("Invalid input")
    expect(page.locator("#cart-error")).not_to_contain_text("quantity")
    assert page.page_errors == []
