"""Exercise staff sign-in, management bearer requests and denial feedback in Chromium.
The real FastAPI app and per-test JSON files decide roles and restaurant ownership.
"""

import os

import pytest

from app.repositories.restaurant import RestaurantRepository

if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip("playwright.sync_api")

from playwright.sync_api import expect  # noqa: E402


def login(page, live_server, account, next_page="create-restaurant.html"):
    page.goto(f"{live_server}/app/staff-sign-in.html?next={next_page}")
    page.get_by_label("Email").fill(account.record.email)
    page.get_by_label("Password").fill(account.password)
    with page.expect_response("**/auth/login") as response:
        page.get_by_role("button", name="Sign in").click()
    assert response.value.status == 200
    token = response.value.json()["access_token"]
    assert "access_token" not in response.value.url
    page.wait_for_url(f"**/app/{next_page}")
    assert page.evaluate("sessionStorage.getItem('food4thought.staff.token')") == token
    return token


def test_admin_sign_in_creates_restaurant_with_bearer_token(page, live_server, auth_accounts):
    token = login(page, live_server, auth_accounts.accounts["administrator"])
    page.get_by_label("Name", exact=True).fill("Session Cafe")
    page.get_by_label("Cuisine", exact=True).fill("Cafe")
    page.get_by_label("Description", exact=True).fill("Breakfast")
    with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/restaurants")) as observed:
        page.get_by_role("button", name="Create restaurant", exact=True).click()
    assert observed.value.status == 201
    assert observed.value.request.header_value("authorization") == f"Bearer {token}"
    expect(page.get_by_role("status")).to_contain_text("Created restaurant")
    assert token not in page.url
    assert page.page_errors == []


def test_wrong_password_never_creates_browser_session(page, live_server, auth_accounts):
    account = auth_accounts.accounts["administrator"]
    page.goto(f"{live_server}/app/staff-sign-in.html")
    page.get_by_label("Email").fill(account.record.email)
    page.get_by_label("Password").fill(account.password + "-wrong")
    with page.expect_response("**/auth/login") as observed:
        page.get_by_role("button", name="Sign in").click()
    assert observed.value.status == 401
    expect(page.get_by_role("alert")).to_contain_text("Invalid email or password")
    assert page.evaluate("sessionStorage.getItem('food4thought.staff.token')") is None
    assert page.get_by_label("Password").input_value() == ""
    assert "password" not in page.url
    assert page.page_errors == []


def test_unsigned_create_request_prompts_sign_in_again(page, live_server, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    page.goto(f"{live_server}/app/create-restaurant.html")
    page.get_by_label("Name", exact=True).fill("No token")
    page.get_by_label("Cuisine", exact=True).fill("Cafe")
    page.get_by_label("Description", exact=True).fill("Not saved")
    with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/restaurants")) as observed:
        page.get_by_role("button", name="Create restaurant", exact=True).click()
    assert observed.value.status == 401
    expect(page.get_by_role("alert")).to_contain_text("sign in again")
    assert isolated_restaurants_path.read_bytes() == before


def test_manager_cannot_create_restaurant(page, live_server, auth_accounts, isolated_restaurants_path):
    token = login(page, live_server, auth_accounts.accounts["restaurant_user"])
    before = isolated_restaurants_path.read_bytes()
    page.get_by_label("Name", exact=True).fill("Not allowed")
    page.get_by_label("Cuisine", exact=True).fill("Cafe")
    page.get_by_label("Description", exact=True).fill("Denied")
    with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/restaurants")) as observed:
        page.get_by_role("button", name="Create restaurant", exact=True).click()
    assert observed.value.status == 403
    assert observed.value.request.header_value("authorization") == f"Bearer {token}"
    expect(page.get_by_role("alert")).to_contain_text("not permitted")
    assert isolated_restaurants_path.read_bytes() == before


def test_manager_cannot_edit_another_restaurant(page, live_server, auth_accounts, isolated_restaurants_path):
    token = login(page, live_server, auth_accounts.accounts["restaurant_user"],
                  "edit-restaurant.html?id=restaurant-002")
    before = isolated_restaurants_path.read_bytes()
    expect(page.get_by_label("Name", exact=True)).to_have_value("Harbour Slice")
    page.get_by_label("Name", exact=True).fill("Not authorized")
    with page.expect_response(lambda r: r.request.method == "PATCH" and r.url.endswith("/restaurants/restaurant-002")) as observed:
        page.get_by_role("button", name="Save changes").click()
    assert observed.value.status == 403
    assert observed.value.request.header_value("authorization") == f"Bearer {token}"
    expect(page.get_by_role("alert")).to_contain_text("not permitted")
    assert isolated_restaurants_path.read_bytes() == before
    assert page.page_errors == []


def test_menu_availability_sends_bearer_and_enforces_ownership(page, live_server, auth_accounts, isolated_restaurants_path):
    token = login(page, live_server, auth_accounts.accounts["restaurant_user"])
    page.goto(f"{live_server}/app/#/restaurants/restaurant-001")
    expect(page.locator("#menu-list li")).to_have_count(2)
    with page.expect_response(lambda r: r.request.method == "PATCH" and "/menu/items/" in r.url) as allowed:
        page.get_by_role("button", name="Mark unavailable").first.click()
    assert allowed.value.status == 200
    assert allowed.value.request.header_value("authorization") == f"Bearer {token}"
    assert allowed.value.request.post_data_json == {"available": False}
    expect(page.get_by_role("button", name="Mark available").first).to_be_visible()
    assert RestaurantRepository(isolated_restaurants_path).get_record("restaurant-001").menu_items[0].available is False

    page.goto(f"{live_server}/app/#/restaurants/restaurant-002")
    expect(page.locator("#menu-list li")).to_have_count(1)
    before = isolated_restaurants_path.read_bytes()
    with page.expect_response(lambda r: r.request.method == "PATCH" and "/menu/items/" in r.url) as denied:
        page.get_by_role("button", name="Mark unavailable").first.click()
    assert denied.value.status == 403
    assert denied.value.request.header_value("authorization") == f"Bearer {token}"
    expect(page.locator("#menu-status")).to_contain_text("not permitted")
    assert isolated_restaurants_path.read_bytes() == before
    assert page.page_errors == []


def test_invalid_session_is_cleared_on_401(page, live_server, isolated_restaurants_path):
    page.goto(f"{live_server}/app/create-restaurant.html")
    page.evaluate("sessionStorage.setItem('food4thought.staff.token', 'expired-or-invalid')")
    page.get_by_label("Name", exact=True).fill("Expired")
    page.get_by_label("Cuisine", exact=True).fill("Cafe")
    page.get_by_label("Description", exact=True).fill("Denied")
    before = isolated_restaurants_path.read_bytes()
    page.get_by_role("button", name="Create restaurant", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("sign in again")
    assert page.evaluate("sessionStorage.getItem('food4thought.staff.token')") is None
    assert isolated_restaurants_path.read_bytes() == before
