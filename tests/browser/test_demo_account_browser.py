"""Verify the login page's demo presets fill editable credentials without submitting.
Exercise each preset through the existing role-aware authentication endpoint.
"""

import os

import pytest

if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip("playwright.sync_api")

from playwright.sync_api import expect  # noqa: E402


@pytest.mark.parametrize(("label", "role", "destination"), [
    ("Demo customer", "customer", None),
    ("Demo manager", "restaurant_user", "**/edit-restaurant.html?id=restaurant-001"),
    ("Demo administrator", "administrator", "**/create-restaurant.html"),
])
def test_demo_button_prefills_then_uses_normal_sign_in(
    page, live_server, auth_accounts, label, role, destination,
):
    credentials = auth_accounts.accounts["customer_a" if role == "customer" else role]
    demo_account = {"email": credentials.record.email, "password": credentials.password}
    if role == "restaurant_user":
        demo_account["restaurant_id"] = "restaurant-001"
    page.route("**/demo-accounts", lambda route: route.fulfill(json={role: demo_account}))
    login_requests = []
    page.on("request", lambda request: login_requests.append(request)
            if request.url.endswith("/auth/login") else None)

    page.goto(f"{live_server}/app/account.html")
    page.get_by_role("button", name=label, exact=True).click()
    form = page.locator("#signin-form")
    expect(form.get_by_label("Email")).to_have_value(credentials.record.email)
    expect(form.get_by_label("Password")).to_have_value(credentials.password)
    expect(form.get_by_label("Password")).to_be_editable()
    expect(page.locator("#register-email")).to_have_value("")
    assert not login_requests

    form.get_by_role("button", name="Sign in", exact=True).click()
    if destination:
        page.wait_for_url(destination)
        assert page.evaluate("sessionStorage.getItem('food4thought.staff.role')") == role
    else:
        expect(page.locator("#profile-email")).to_have_text(credentials.record.email)
    assert len(login_requests) == 1
