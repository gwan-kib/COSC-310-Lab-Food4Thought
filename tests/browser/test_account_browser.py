"""End-to-end customer account UI tests against contract-shaped responses and the
real API. Root fixtures isolate every JSON store and guard committed data.
"""
import json
import os

import pytest

if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip("playwright.sync_api", reason="Playwright is not installed")

from playwright.sync_api import expect  # noqa: E402

ACCOUNT = "/app/account.html"
PROFILE = "**/customers/me"


def open_account(page, live_server):
    page.goto(f"{live_server}{ACCOUNT}")
    expect(page.get_by_role("heading", name="Create a customer account")).to_be_visible()


def register_fields(page, name="Casey Tester", email="casey@example.invalid",
                    address="42 Test Street", password="casey-password-123"):
    form = page.locator("#register-form")
    form.get_by_label("Name").fill(name)
    form.get_by_label("Email").fill(email)
    form.get_by_label("Delivery address").fill(address)
    form.get_by_label("Password").fill(password)


def sign_in(page, email, password):
    form = page.locator("#signin-form")
    form.get_by_label("Email").fill(email)
    form.get_by_label("Password").fill(password)
    form.get_by_role("button", name="Sign in").click()


def account_sign_in(page, live_server, auth_accounts, key="customer_a"):
    open_account(page, live_server)
    account = auth_accounts.accounts[key]
    sign_in(page, account.record.email, account.password)
    expect(page.locator("#profile-email")).to_have_text(account.record.email)
    return account


def test_navigation_and_mock_contract_support_register_signin_and_profile(page, live_server):
    page.goto(f"{live_server}/app/")
    page.get_by_role("link", name="My account").click()
    expect(page).to_have_url(f"{live_server}{ACCOUNT}")
    calls = []

    def mock_contract(route):
        req = route.request
        calls.append((req.method, req.url, req.post_data_json, req.header_value("authorization")))
        if req.url.endswith("/customers"):
            route.fulfill(status=201, json={"id": "mock-id", "name": "Casey Tester",
                "email": "casey@example.invalid", "delivery_address": "42 Test Street",
                "status": "active"})
        elif req.url.endswith("/auth/login"):
            route.fulfill(status=200, json={"access_token": "mock-token", "token_type": "bearer",
                "role": "customer"})
        else:
            route.fulfill(status=200, json={"id": "mock-id", "name": "Casey Tester",
                "email": "casey@example.invalid", "delivery_address": "42 Test Street",
                "status": "active"})

    page.route("**/customers", mock_contract)
    page.route("**/auth/login", mock_contract)
    page.route(PROFILE, mock_contract)
    register_fields(page)
    page.locator("#register-form").get_by_role("button", name="Register").click()
    expect(page.locator("#register-status")).to_contain_text("Account created")
    sign_in(page, "casey@example.invalid", "casey-password-123")
    expect(page.locator("#saved-name")).to_have_text("Casey Tester")
    assert calls[0][2]["password"] == "casey-password-123"
    assert calls[1][2] == {"email": "casey@example.invalid", "password": "casey-password-123"}
    assert calls[2][3] == "Bearer mock-token"
    assert page.page_errors == []


def test_registration_login_and_profile_survive_navigation(page, live_server, m2_store_paths):
    open_account(page, live_server)
    register_fields(page)
    with page.expect_response("**/customers") as response:
        page.locator("#register-form").get_by_role("button", name="Register").click()
    assert response.value.status == 201
    expect(page.locator("#register-status")).to_contain_text("Account created")
    assert len(json.loads(m2_store_paths["customers"].read_text())) == 1
    stored = json.loads(m2_store_paths["customers"].read_text())[0]
    assert stored["password_hash"].startswith("$argon2id$")
    assert "casey-password-123" not in m2_store_paths["customers"].read_text()
    sign_in(page, "casey@example.invalid", "casey-password-123")
    expect(page.locator("#saved-address")).to_have_text("42 Test Street")
    assert page.evaluate("sessionStorage.getItem('food4thought.customer.token')") is not None
    page.get_by_role("link", name="Browse restaurants").click()
    expect(page.locator("#restaurant-list button")).to_have_count(2)
    page.get_by_role("link", name="My account").click()
    expect(page.locator("#profile-email")).to_have_text("casey@example.invalid")
    assert page.page_errors == []


def test_validation_duplicate_email_and_wrong_password(page, live_server, auth_accounts, m2_store_paths):
    open_account(page, live_server)
    original = m2_store_paths["customers"].read_bytes()
    register_fields(page, name="   ", email=auth_accounts.accounts["customer_a"].record.email)
    page.locator("#register-form").get_by_role("button", name="Register").click()
    expect(page.locator("#register-errors")).to_contain_text("Name")
    expect(page.locator("#register-form [name=name]")).to_have_attribute("aria-invalid", "true")
    assert m2_store_paths["customers"].read_bytes() == original
    page.locator("#register-form [name=name]").fill("Casey")
    page.locator("#register-form").get_by_role("button", name="Register").click()
    expect(page.locator("#register-errors")).to_contain_text("Email is already registered")
    assert m2_store_paths["customers"].read_bytes() == original

    sign_in(page, auth_accounts.accounts["customer_a"].record.email, "wrong-password-1")
    expect(page.locator("#signin-errors")).to_contain_text("Invalid email or password")
    expect(page.locator("#signin-form [name=password]")).to_have_value("wrong-password-1")
    expect(page.locator("#signed-out")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('food4thought.customer.token')") is None


def test_expired_token_prompts_signin_and_does_not_expose_profile(page, live_server, auth_accounts):
    page.goto(f"{live_server}/app/")
    page.evaluate("(value) => sessionStorage.setItem('food4thought.customer.token', value)",
                  auth_accounts.expired_token)
    page.goto(f"{live_server}{ACCOUNT}")
    expect(page.locator("#session-status")).to_contain_text("expired")
    expect(page.locator("#signed-out")).to_be_visible()
    expect(page.locator("#signed-in")).to_be_hidden()
    assert page.evaluate("sessionStorage.getItem('food4thought.customer.token')") is None


def test_staff_login_cannot_use_customer_profile(page, live_server, auth_accounts):
    open_account(page, live_server)
    account = auth_accounts.accounts["restaurant_user"]
    sign_in(page, account.record.email, account.password)
    expect(page.locator("#signin-errors")).to_contain_text("customer accounts")
    expect(page.locator("#signed-out")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem('food4thought.customer.token')") is None


def test_profile_update_persists_and_refresh_preserves_unsaved_edits(
    page, live_server, auth_accounts, m2_store_paths
):
    account = account_sign_in(page, live_server, auth_accounts)
    form = page.locator("#profile-form")
    form.get_by_label("Name").fill("Updated Customer")
    form.get_by_label("Delivery address").fill("99 Revised Road")
    with page.expect_response(lambda r: r.request.method == "PATCH" and "/customers/me" in r.url) as response:
        form.get_by_role("button", name="Save changes").click()
    assert response.value.status == 200
    expect(page.locator("#profile-status")).to_contain_text("Profile updated")
    stored = json.loads(m2_store_paths["customers"].read_text())
    updated = next(c for c in stored if c["id"] == account.record.id)
    assert updated["name"] == "Updated Customer"
    assert updated["delivery_address"] == "99 Revised Road"
    assert updated["email"] == account.record.email
    form.get_by_label("Name").fill("Not yet saved")
    page.get_by_role("button", name="Check saved profile").click()
    expect(page.locator("#saved-name")).to_have_text("Updated Customer")
    expect(form.get_by_label("Name")).to_have_value("Not yet saved")
    assert page.page_errors == []


def test_deactivation_is_confirmed_read_only_and_backend_denies_updates(
    page, live_server, auth_accounts, m2_store_paths
):
    account = account_sign_in(page, live_server, auth_accounts)
    page.locator("#deactivate-form").get_by_role("button", name="Deactivate my account").click()
    expect(page.locator("#deactivate-form")).to_be_visible()  # Required checkbox blocks request.
    page.locator("#confirm-deactivate").check()
    with page.expect_response("**/customers/me/deactivate") as response:
        page.locator("#deactivate-form").get_by_role("button", name="Deactivate my account").click()
    assert response.value.status == 200
    expect(page.locator("#account-state")).to_contain_text("inactive")
    expect(page.locator("#profile-form")).to_be_hidden()
    expect(page.locator("#deactivate-form")).to_be_hidden()
    saved = next(c for c in json.loads(m2_store_paths["customers"].read_text())
                 if c["id"] == account.record.id)
    assert saved["status"] == "inactive"
    token = page.evaluate("sessionStorage.getItem('food4thought.customer.token')")
    denied = page.request.patch(f"{live_server}/customers/me",
        data={"name": "Not allowed"}, headers={"Authorization": f"Bearer {token}"})
    assert denied.status == 403
    page.reload()
    expect(page.locator("#account-state")).to_contain_text("inactive")
    expect(page.locator("#saved-name")).to_have_text(account.record.name)
    assert page.page_errors == []


def test_write_lost_response_preserves_edits_and_never_retries(page, live_server, auth_accounts):
    account_sign_in(page, live_server, auth_accounts)
    attempts = []

    def lose_response(route):
        attempts.append(route.request)
        route.fetch()  # The backend saves; browser never gets confirmation.
        route.abort()

    page.route(PROFILE, lambda route: lose_response(route) if route.request.method == "PATCH"
               else route.continue_())
    form = page.locator("#profile-form")
    form.get_by_label("Name").fill("Changed, confirmation lost")
    form.get_by_role("button", name="Save changes").click()
    expect(page.locator("#profile-errors")).to_contain_text("Check saved profile")
    expect(form.get_by_label("Name")).to_have_value("Changed, confirmation lost")
    page.wait_for_timeout(250)
    assert len(attempts) == 1
    page.get_by_role("button", name="Check saved profile").click()
    expect(page.locator("#saved-name")).to_have_text("Changed, confirmation lost")
    assert len(attempts) == 1
    assert page.page_errors == []


def test_pending_registration_cannot_send_duplicate_posts(page, live_server, m2_store_paths):
    held = []
    page.route("**/customers", lambda route: held.append(route))
    open_account(page, live_server)
    register_fields(page)
    button = page.locator("#register-form").get_by_role("button", name="Register")
    button.click()
    expect(button).to_be_disabled()
    page.locator("#register-form").evaluate(
        "form => form.dispatchEvent(new Event('submit', {cancelable: true}))"
    )
    page.wait_for_timeout(200)
    assert len(held) == 1
    held[0].continue_()
    expect(page.locator("#register-status")).to_contain_text("Account created")
    assert len(json.loads(m2_store_paths["customers"].read_text())) == 1


def test_ambiguous_registration_preserves_inputs_for_manual_verification(page, live_server):
    page.route("**/customers", lambda route: route.abort())
    open_account(page, live_server)
    register_fields(page)
    page.locator("#register-form").get_by_role("button", name="Register").click()
    expect(page.locator("#register-errors")).to_contain_text("Try signing in to verify")
    expect(page.locator("#register-form [name=name]")).to_have_value("Casey Tester")
    expect(page.locator("#register-form [name=password]")).to_have_value("casey-password-123")
    assert page.page_errors == []


def test_profile_403_after_external_deactivation_is_reflected(page, live_server, auth_accounts):
    account_sign_in(page, live_server, auth_accounts)
    token = page.evaluate("sessionStorage.getItem('food4thought.customer.token')")
    result = page.request.post(f"{live_server}/customers/me/deactivate",
        headers={"Authorization": f"Bearer {token}"})
    assert result.status == 200
    form = page.locator("#profile-form")
    form.get_by_label("Name").fill("Unsubmitted edit")
    form.get_by_role("button", name="Save changes").click()
    expect(page.locator("#account-state")).to_contain_text("inactive")
    expect(page.locator("#profile-form")).to_be_hidden()
    assert page.page_errors == []


def test_api_display_escapes_text_and_mobile_layout_supports_keyboard(page, live_server):
    page.set_viewport_size({"width": 390, "height": 844})
    open_account(page, live_server)
    payload = '<img src=x onerror="window.injected=true"> A'
    register_fields(page, name=payload)
    page.locator("#register-form").get_by_role("button", name="Register").click()
    sign_in(page, "casey@example.invalid", "casey-password-123")
    expect(page.locator("#saved-name")).to_have_text(payload)
    assert page.locator("#signed-in img").count() == 0
    assert page.evaluate("window.injected") is None
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.page_errors == []
