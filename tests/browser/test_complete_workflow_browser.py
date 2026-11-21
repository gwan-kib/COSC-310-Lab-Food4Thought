"""Verify a customer can register, sign in and buy through Food4Thought's real UI.
Chromium drives the account, menu and cart pages against the actual REST API
and isolated JSON stores; order details are verified after browser checkout.
"""

import json
import os

import pytest

if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip("playwright.sync_api", reason="Playwright is not installed")

from playwright.sync_api import expect  # noqa: E402

from app.repositories.order import OrderRepository


def test_browser_registration_to_order_receipt_and_owned_api_detail(
        page, live_server, m2_store_paths):
    name = "Browser Workflow"
    email = "browser-workflow@example.invalid"
    password = "browser-workflow-password"
    address = "77 Browser Test Street"

    page.goto(f"{live_server}/app/account.html")
    form = page.locator("#register-form")
    form.get_by_label("Name").fill(name)
    form.get_by_label("Email").fill(email)
    form.get_by_label("Delivery address").fill(address)
    form.get_by_label("Password").fill(password)
    with page.expect_response("**/customers") as registered:
        form.get_by_role("button", name="Register").click()
    assert registered.value.status == 201
    account = registered.value.json()
    expect(page.locator("#register-status")).to_contain_text("Account created")

    sign_in = page.locator("#signin-form")
    sign_in.get_by_label("Email").fill(email)
    sign_in.get_by_label("Password").fill(password)
    with page.expect_response("**/auth/login") as logged_in:
        sign_in.get_by_role("button", name="Sign in").click()
    assert logged_in.value.status == 200
    expect(page.locator("#profile-email")).to_have_text(email)

    page.get_by_role("link", name="Browse restaurants").click()
    expect(page.locator("#restaurant-list button")).to_have_count(2)
    page.locator("#restaurant-list button[data-restaurant-id='restaurant-001']").click()
    expect(page.locator("#menu-list li")).to_have_count(2)
    with page.expect_response("**/customers/me/cart/items") as added:
        page.get_by_role("button", name="Add Vegetable bowl to cart").click()
    assert added.value.status == 200
    expect(page.locator("#menu-status")).to_contain_text("Added Vegetable bowl")

    page.get_by_role("link", name="My cart").click()
    expect(page.locator("#cart-items li")).to_have_count(1)
    expect(page.locator("#cart-total")).to_have_text("$12.50")
    page.get_by_role("spinbutton", name="Quantity for Vegetable bowl").fill("2")
    with page.expect_response("**/customers/me/cart/items/item-001") as changed:
        page.get_by_role("button", name="Update quantity for Vegetable bowl").click()
    assert changed.value.status == 200
    cart = changed.value.json()
    expect(page.locator("#cart-total")).to_have_text("$25.00")

    with page.expect_response("**/customers/me/checkout") as checkout:
        page.get_by_role("button", name="Place order").click()
    assert checkout.value.status == 201
    receipt = checkout.value.json()["order"]
    expect(page.locator("#order-confirmation")).to_be_visible()
    expect(page.locator("#order-id")).to_have_text(receipt["id"])
    expect(page.locator("#order-total")).to_have_text("$25.00")
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    assert (receipt["customer_id"], receipt["source_cart_id"],
            receipt["source_cart_revision"], receipt["delivery_address"],
            receipt["total"]) == (
                account["id"], cart["id"], cart["revision"], address, "25.00")

    saved = OrderRepository(m2_store_paths["orders"]).get_order(receipt["id"])
    assert saved is not None and saved.model_dump(mode="json") == receipt
    assert json.loads(m2_store_paths["orders"].read_text(encoding="utf-8")) == [receipt]
    token = page.evaluate("sessionStorage.getItem('food4thought.customer.token')")
    assert token
    detail = page.request.get(f"{live_server}/customers/me/orders/{receipt['id']}",
                              headers={"Authorization": f"Bearer {token}"})
    assert detail.status == 200 and detail.json() == receipt

    page.reload()
    expect(page.locator("#cart-total")).to_have_text("$0.00")
    assert len(json.loads(m2_store_paths["orders"].read_text())) == 1
    assert page.page_errors == []
