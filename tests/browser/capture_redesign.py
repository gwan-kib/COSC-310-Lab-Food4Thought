"""Capture representative Food4Thought screens using the real browser test fixtures."""

from pathlib import Path

from playwright.sync_api import expect


def test_capture_redesign(page, live_server, auth_accounts):
    output = Path("redesign-screenshots")
    output.mkdir(exist_ok=True)
    app = f"{live_server}/app/"

    def capture(name, width, height):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        page.screenshot(path=output / f"{name}.png", full_page=True)

    page.goto(app)
    expect(page.locator("#restaurant-list li")).to_have_count(2)
    capture("desktop-discovery", 1440, 1000)

    page.goto(app + "#/restaurants/restaurant-001")
    expect(page.locator("#menu-list li")).to_have_count(2)
    capture("mobile-menu", 390, 844)

    customer = auth_accounts.accounts["customer_a"]
    page.goto(app + "account.html")
    form = page.locator("#signin-form")
    form.get_by_label("Email").fill(customer.record.email)
    form.get_by_label("Password").fill(customer.password)
    form.get_by_role("button", name="Sign in").click()
    expect(page.locator("#profile-email")).to_have_text(customer.record.email)
    page.goto(app + "#/restaurants/restaurant-001")
    page.get_by_role("button", name="Add Vegetable bowl to cart").click()
    expect(page.locator("#menu-status")).to_contain_text("Added Vegetable bowl")
    page.get_by_role("link", name="My cart").click()
    expect(page.locator("#cart-total")).to_have_text("$12.50")
    capture("mobile-cart", 390, 844)

    manager = auth_accounts.accounts["restaurant_user"]
    page.goto(app + "staff-sign-in.html?next=edit-restaurant.html%3Fid%3Drestaurant-001")
    page.get_by_label("Email").fill(manager.record.email)
    page.get_by_label("Password").fill(manager.password)
    page.get_by_role("button", name="Sign in").click()
    expect(page.locator("#management-menu li")).to_have_count(2)
    expect(page.get_by_role("button", name="Mark unavailable for Vegetable bowl")).to_be_visible()
    capture("desktop-staff", 1440, 1000)
