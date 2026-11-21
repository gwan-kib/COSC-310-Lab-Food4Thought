"""Regression tests for PR #118 review: credentials, session isolation and profile races.

Every browser test uses isolated M2 stores via the shared pytest fixtures.
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
    expect(page.locator("#signin-form")).to_be_visible()


def sign_in(page, account):
    page.locator("#signin-form [name=email]").fill(account.record.email)
    page.locator("#signin-form [name=password]").fill(account.password)
    page.locator("#signin-form button[type=submit]").click()
    expect(page.locator("#saved-address")).to_have_text(account.record.delivery_address)


def token(page):
    return page.evaluate("sessionStorage.getItem('food4thought.customer.token')")


def test_forms_do_not_submit_credentials_if_javascript_is_unavailable(page, live_server):
    page.route("**/account.js", lambda route: route.abort())
    open_account(page, live_server)
    for form_id in ("signin-form", "register-form"):
        form = page.locator(f"#{form_id}")
        expect(form).to_have_attribute("method", "post")
        expect(form.locator("fieldset")).to_be_disabled()
        expect(form.locator("button[type=submit]")).to_be_disabled()
    page.unroute("**/account.js")
    page.reload()
    expect(page.locator("#signin-form fieldset")).to_be_enabled()
    expect(page.locator("#register-form fieldset")).to_be_enabled()


def test_switching_accounts_discards_saved_profile_and_deactivation_consent(
    page, live_server, auth_accounts
):
    open_account(page, live_server)
    sign_in(page, auth_accounts.accounts["customer_a"])
    page.locator("#confirm-deactivate").check()
    page.get_by_role("button", name="Sign out of this tab").click()

    expect(page.locator("#profile-email")).to_be_empty()
    expect(page.locator("#saved-name")).to_be_empty()
    expect(page.locator("#saved-address")).to_be_empty()
    expect(page.locator("#profile-form [name=delivery_address]")).to_have_value("")
    expect(page.locator("#confirm-deactivate")).not_to_be_checked()

    # B authenticates but their profile GET fails: never show A's information.
    page.route(PROFILE, lambda route: route.fulfill(
        status=500, json={"detail": "Customer data is unavailable"}
    ))
    account_b = auth_accounts.accounts["customer_b"]
    page.locator("#signin-form [name=email]").fill(account_b.record.email)
    page.locator("#signin-form [name=password]").fill(account_b.password)
    page.locator("#signin-form button[type=submit]").click()
    expect(page.locator("#refresh-errors")).to_contain_text("Customer data is unavailable")
    expect(page.locator("#profile-details")).to_be_hidden()
    expect(page.locator("#profile-form")).to_be_hidden()
    expect(page.locator("#confirm-deactivate")).not_to_be_checked()
    expect(page.locator("#saved-address")).to_be_empty()


def test_expired_session_clears_all_profile_information(page, live_server, auth_accounts):
    open_account(page, live_server)
    sign_in(page, auth_accounts.accounts["customer_a"])
    page.locator("#confirm-deactivate").check()
    page.route(PROFILE, lambda route: route.fulfill(
        status=401, json={"detail": "Authentication required"}
    ))
    page.get_by_role("button", name="Check saved profile").click()
    expect(page.locator("#session-status")).to_contain_text("expired")
    expect(page.locator("#profile-email")).to_be_empty()
    expect(page.locator("#saved-address")).to_be_empty()
    expect(page.locator("#confirm-deactivate")).not_to_be_checked()
    assert token(page) is None


def test_refresh_merges_external_changes_without_overwriting_untouched_field(
    page, live_server, auth_accounts, m2_store_paths
):
    open_account(page, live_server)
    account = auth_accounts.accounts["customer_a"]
    sign_in(page, account)
    page.locator("#profile-form [name=name]").fill("Local name edit")

    response = page.request.patch(
        f"{live_server}/customers/me",
        data={"delivery_address": "Externally revised address"},
        headers={"Authorization": f"Bearer {token(page)}"},
    )
    assert response.status == 200
    page.get_by_role("button", name="Check saved profile").click()
    expect(page.locator("#saved-address")).to_have_text("Externally revised address")
    expect(page.locator("#profile-form [name=name]")).to_have_value("Local name edit")
    expect(page.locator("#profile-form [name=delivery_address]")).to_have_value(
        "Externally revised address"
    )

    with page.expect_request(lambda request: request.method == "PATCH" and
                             request.url.endswith("/customers/me")) as saved_request:
        page.locator("#profile-form button[type=submit]").click()
    assert saved_request.value.post_data_json == {"name": "Local name edit"}
    expect(page.locator("#profile-status")).to_contain_text("Profile updated")

    stored = next(item for item in json.loads(m2_store_paths["customers"].read_text())
                  if item["id"] == account.record.id)
    assert stored["delivery_address"] == "Externally revised address"
    assert stored["name"] == "Local name edit"


def test_multiline_original_name_not_rewritten_by_address_only_patch(
    page, live_server, auth_accounts, m2_store_paths
):
    records = json.loads(m2_store_paths["customers"].read_text())
    records[0]["name"] = "First line\\nSecond line".replace("\\n", "\n")
    original_name = records[0]["name"]
    m2_store_paths["customers"].write_text(json.dumps(records), encoding="utf-8")
    open_account(page, live_server)
    sign_in(page, auth_accounts.accounts["customer_a"])
    page.locator("#profile-form [name=delivery_address]").fill("New address")
    with page.expect_request(lambda request: request.method == "PATCH" and
                             request.url.endswith("/customers/me")) as saved_request:
        page.locator("#profile-form button[type=submit]").click()
    assert saved_request.value.post_data_json == {"delivery_address": "New address"}
    expect(page.locator("#profile-status")).to_contain_text("Profile updated")
    updated = json.loads(m2_store_paths["customers"].read_text())[0]
    assert updated["name"] == original_name


def test_stale_refresh_cannot_reactivate_profile_after_deactivation(
    page, live_server, auth_accounts
):
    open_account(page, live_server)
    sign_in(page, auth_accounts.accounts["customer_a"])
    held = []
    page.route(PROFILE, lambda route: held.append(route) if route.request.method == "GET"
               else route.continue_())
    with page.expect_request(lambda request: request.method == "GET" and
                             request.url.endswith("/customers/me")):
        page.get_by_role("button", name="Check saved profile").click()
    for _ in range(100):
        if held:
            break
        page.wait_for_timeout(20)
    assert len(held) == 1
    page.locator("#confirm-deactivate").check()
    page.locator("#deactivate-form button[type=submit]").click()
    expect(page.locator("#account-state")).to_contain_text("inactive")
    expect(page.locator("#profile-form")).to_be_hidden()

    stale = auth_accounts.accounts["customer_a"].record.public().model_dump(mode="json")
    held[0].fulfill(status=200, json=stale)
    page.wait_for_timeout(250)
    expect(page.locator("#account-state")).to_contain_text("inactive")
    expect(page.locator("#profile-form")).to_be_hidden()
    assert page.page_errors == []


def test_first_successful_profile_fetch_populates_form_after_initial_failure(
    page, live_server, auth_accounts
):
    page.route(PROFILE, lambda route: route.abort())
    open_account(page, live_server)
    account = auth_accounts.accounts["customer_a"]
    page.locator("#signin-form [name=email]").fill(account.record.email)
    page.locator("#signin-form [name=password]").fill(account.password)
    page.locator("#signin-form button[type=submit]").click()
    expect(page.locator("#refresh-errors")).to_contain_text("Could not reach the server")
    expect(page.locator("#profile-form")).to_be_hidden()
    page.unroute(PROFILE)
    page.get_by_role("button", name="Check saved profile").click()
    expect(page.locator("#saved-name")).to_have_text(account.record.name)
    expect(page.locator("#profile-form [name=name]")).to_have_value(account.record.name)
    expect(page.locator("#profile-form [name=delivery_address]")).to_have_value(
        account.record.delivery_address
    )
    assert page.page_errors == []
