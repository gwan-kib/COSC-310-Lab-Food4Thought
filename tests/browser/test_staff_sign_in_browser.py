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
    assert "access_token" not in response.value.url
    page.wait_for_url(f"**/app/{next_page}")
    # The form navigates immediately on success, so Chromium may discard the
    # login response body. Read the token from the destination tab instead.
    token = page.evaluate("sessionStorage.getItem('food4thought.staff.token')")
    assert isinstance(token, str) and token
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


def test_unsigned_create_is_read_only_with_sign_in_guidance(page, live_server, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    page.goto(f"{live_server}/app/create-restaurant.html")
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_disabled()
    expect(page.locator("#create-access")).to_contain_text("Sign in")
    assert isolated_restaurants_path.read_bytes() == before


def test_manager_cannot_create_restaurant(page, live_server, auth_accounts, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    login(page, live_server, auth_accounts.accounts["restaurant_user"])
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_disabled()
    expect(page.locator("#create-access")).to_contain_text("administrator")
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


@pytest.mark.parametrize("customer_signed_in", [False, True])
def test_public_menu_is_read_only(page, live_server, auth_accounts, customer_signed_in):
    if customer_signed_in:
        account = auth_accounts.accounts["customer_a"]
        page.goto(f"{live_server}/app/account.html")
        form = page.locator("#signin-form")
        form.get_by_label("Email").fill(account.record.email)
        form.get_by_label("Password").fill(account.password)
        form.get_by_role("button", name="Sign in").click()
        expect(page.locator("#profile-email")).to_have_text(account.record.email)

    page.goto(f"{live_server}/app/#/restaurants/restaurant-001")
    expect(page.get_by_text("Available", exact=True)).to_have_count(2)
    expect(page.get_by_role("button", name="Mark unavailable")).to_have_count(0)
    expect(page.get_by_role("button", name="Mark available", exact=False)).to_have_count(0)


@pytest.mark.parametrize("signed_in_admin", [False, True])
def test_editor_explains_known_lack_of_access(page, live_server, auth_accounts, signed_in_admin):
    editor = "edit-restaurant.html?id=restaurant-001"
    if signed_in_admin:
        login(page, live_server, auth_accounts.accounts["administrator"], editor)
    else:
        page.goto(f"{live_server}/app/{editor}")
    expect(page.locator("#management-menu li")).to_have_count(2)
    expect(page.get_by_role("button", name="Mark unavailable")).to_have_count(0)
    expect(page.locator("#edit-access")).to_contain_text(
        "restaurant manager" if signed_in_admin else "Sign in"
    )
    expect(page.get_by_role("button", name="Save changes")).to_be_disabled()


def test_menu_availability_sends_bearer_and_enforces_ownership(page, live_server, auth_accounts, isolated_restaurants_path):
    editor = "edit-restaurant.html?id=restaurant-001"
    token = login(page, live_server, auth_accounts.accounts["restaurant_user"], editor)
    with page.expect_response(lambda r: r.request.method == "PATCH" and "/menu/items/" in r.url) as allowed:
        page.get_by_role("button", name="Mark unavailable for Vegetable bowl").click()
    assert allowed.value.status == 200
    assert allowed.value.request.header_value("authorization") == f"Bearer {token}"
    assert allowed.value.request.post_data_json == {"available": False}
    expect(page.get_by_role("button", name="Mark available for Vegetable bowl")).to_be_visible()
    assert RestaurantRepository(isolated_restaurants_path).get_record("restaurant-001").menu_items[0].available is False

    page.get_by_role("link", name="Back to restaurant").click()
    expect(page.get_by_text("Unavailable", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Add Vegetable bowl to cart")).to_be_disabled()
    expect(page.get_by_role("button", name="Mark available for Vegetable bowl")).to_have_count(0)

    page.get_by_role("link", name="Edit restaurant").click()
    with page.expect_response(lambda r: r.request.method == "PATCH" and "/menu/items/" in r.url) as restored:
        page.get_by_role("button", name="Mark available for Vegetable bowl").click()
    assert restored.value.status == 200
    assert restored.value.request.post_data_json == {"available": True}

    page.goto(f"{live_server}/app/edit-restaurant.html?id=restaurant-002")
    expect(page.locator("#management-menu li")).to_have_count(2)
    before = isolated_restaurants_path.read_bytes()
    with page.expect_response(lambda r: r.request.method == "PATCH" and "/menu/items/" in r.url) as denied:
        page.get_by_role("button", name="Mark unavailable").first.click()
    assert denied.value.status == 403
    assert denied.value.request.header_value("authorization") == f"Bearer {token}"
    expect(page.locator("#edit-access")).to_contain_text("not permitted")
    expect(page.get_by_role("button", name="Save changes")).to_be_disabled()
    expect(page.get_by_role("button", name="Mark unavailable")).to_have_count(0)
    assert isolated_restaurants_path.read_bytes() == before
    assert page.page_errors == []


def test_invalid_session_is_cleared_on_401(page, live_server, isolated_restaurants_path):
    page.add_init_script("sessionStorage.setItem('food4thought.staff.token', 'expired-or-invalid')")
    page.goto(f"{live_server}/app/create-restaurant.html")
    page.get_by_label("Name", exact=True).fill("Expired")
    page.get_by_label("Cuisine", exact=True).fill("Cafe")
    page.get_by_label("Description", exact=True).fill("Denied")
    before = isolated_restaurants_path.read_bytes()
    page.get_by_role("button", name="Create restaurant", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("sign in again")
    assert page.evaluate("sessionStorage.getItem('food4thought.staff.token')") is None
    assert isolated_restaurants_path.read_bytes() == before
