# Verify Food4Thought's Edit restaurant page using Chromium, the real API, and
# isolated JSON storage.
# Cover navigation, PATCH persistence, partial payloads, validation, missing records,
# request failures, timeout recovery, safe rendering, and narrow screens.

"""Browser regression tests for editing an existing restaurant."""

import json
import os

import pytest

from app.repositories.restaurant import RestaurantRepository

if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip("playwright.sync_api")

from playwright.sync_api import expect  # noqa: E402


DETAILS_PATH = "**/restaurants/restaurant-001"


def open_editor(page, live_server, restaurant_id="restaurant-001"):
    page.goto(f"{live_server}/app/edit-restaurant.html?id={restaurant_id}")
    expect(page.get_by_label("Name", exact=True)).to_have_value(
        "Cedar Bowl", timeout=5000
    )


def test_selected_restaurant_links_to_prefilled_editor(page, live_server):
    page.goto(f"{live_server}/app/#/restaurants/restaurant-001")
    expect(page.locator("#details-name")).to_have_text("Cedar Bowl")
    link = page.get_by_role("link", name="Edit restaurant", exact=True)
    expect(link).to_have_attribute(
        "href", "edit-restaurant.html?id=restaurant-001"
    )
    link.click()
    expect(page.get_by_label("Name", exact=True)).to_have_value("Cedar Bowl")
    expect(page.get_by_label("Cuisine", exact=True)).to_have_value("Japanese")
    expect(page.get_by_label("Description", exact=True)).to_have_value(
        "Rice bowls and noodles"
    )
    expect(page.get_by_role("link", name="Back to restaurant")).to_have_attribute(
        "href", "./#/restaurants/restaurant-001"
    )
    assert page.page_errors == []


def test_partial_patch_persists_without_changing_id_or_menu(
    page, live_server, isolated_restaurants_path
):
    before = RestaurantRepository(isolated_restaurants_path).load_records()
    open_editor(page, live_server)
    page.get_by_label("Name", exact=True).fill("  Updated Bowl  ")
    page.get_by_label("Description", exact=True).fill("New seasonal menu")
    with page.expect_response(
        lambda response: response.request.method == "PATCH"
    ) as update:
        page.get_by_role("button", name="Save changes").click()
    response = update.value
    assert response.status == 200
    assert response.request.post_data_json == {
        "name": "  Updated Bowl  ",
        "description": "New seasonal menu",
    }
    expect(page.get_by_role("status")).to_contain_text("saved")
    after = RestaurantRepository(isolated_restaurants_path).load_records()
    assert len(after) == len(before)
    assert after[0].id == before[0].id
    assert after[0].menu_items == before[0].menu_items
    assert after[1:] == before[1:]
    assert after[0].name == "Updated Bowl"
    assert after[0].cuisine == "Japanese"
    assert after[0].description == "New seasonal menu"
    page.get_by_role("link", name="Back to restaurant").click()
    expect(page.locator("#details-name")).to_have_text("Updated Bowl")
    expect(page.locator("#details-description")).to_have_text("New seasonal menu")
    assert page.page_errors == []


def test_unchanged_form_does_not_send_empty_patch(page, live_server, isolated_restaurants_path):
    original = isolated_restaurants_path.read_bytes()
    patches = []
    page.on("request", lambda req: patches.append(req) if req.method == "PATCH" else None)
    open_editor(page, live_server)
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_role("status")).to_contain_text("No changes")
    assert patches == []
    assert isolated_restaurants_path.read_bytes() == original


def test_invalid_values_display_backend_field_errors_and_recover(
    page, live_server, isolated_restaurants_path
):
    before = isolated_restaurants_path.read_bytes()
    open_editor(page, live_server)
    page.get_by_label("Name", exact=True).fill("   ")
    with page.expect_response(
        lambda response: response.request.method == "PATCH"
    ) as bad:
        page.get_by_role("button", name="Save changes").click()
    assert bad.value.status == 422
    expect(page.get_by_role("alert")).to_contain_text("Name")
    expect(page.get_by_label("Name", exact=True)).to_have_attribute(
        "aria-invalid", "true"
    )
    assert isolated_restaurants_path.read_bytes() == before
    page.get_by_label("Name", exact=True).fill("Cedar and Pine")
    expect(page.get_by_label("Name", exact=True)).not_to_have_attribute(
        "aria-invalid", "true"
    )
    with page.expect_response(
        lambda response: response.request.method == "PATCH"
    ) as good:
        page.get_by_role("button", name="Save changes").click()
    assert good.value.status == 200
    expect(page.get_by_role("alert", include_hidden=True)).to_be_empty()
    expect(page.get_by_role("status")).to_contain_text("saved")


def test_unknown_restaurant_and_invalid_link_do_not_enable_editing(page, live_server):
    page.goto(f"{live_server}/app/edit-restaurant.html?id=missing")
    expect(page.get_by_role("alert")).to_contain_text("doesn't exist")
    expect(page.get_by_role("button", name="Save changes")).to_be_disabled()
    page.goto(f"{live_server}/app/edit-restaurant.html")
    expect(page.get_by_role("alert")).to_contain_text("Select a restaurant")
    expect(page.get_by_role("button", name="Save changes")).to_be_disabled()
    assert page.page_errors == []


def test_loading_failure_and_retry_preserve_safe_read_only_state(page, live_server):
    def fail_read(route):
        route.fulfill(
            status=500, content_type="application/json",
            body=json.dumps({"detail": "Restaurant data is unavailable"}),
        )

    page.route(DETAILS_PATH, fail_read)
    page.goto(f"{live_server}/app/edit-restaurant.html?id=restaurant-001")
    expect(page.get_by_role("alert")).to_contain_text("Restaurant data is unavailable")
    expect(page.get_by_role("button", name="Save changes")).to_be_disabled()
    page.unroute(DETAILS_PATH)
    page.get_by_role("button", name="Retry loading").click()
    expect(page.get_by_label("Name", exact=True)).to_have_value("Cedar Bowl")


def test_patch_failure_keeps_edits_and_allows_explicit_retry(
    page, live_server, isolated_restaurants_path
):
    original = isolated_restaurants_path.read_bytes()
    open_editor(page, live_server)
    page.get_by_label("Cuisine", exact=True).fill("Fusion")

    def fail_patch(route):
        if route.request.method == "PATCH":
            route.fulfill(
                status=500, content_type="application/json",
                body=json.dumps({"detail": "Restaurant data is unavailable"}),
            )
        else:
            route.continue_()

    page.route(DETAILS_PATH, fail_patch)
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_role("alert")).to_contain_text("Restaurant data is unavailable")
    expect(page.get_by_label("Cuisine", exact=True)).to_have_value("Fusion")
    assert isolated_restaurants_path.read_bytes() == original
    page.unroute(DETAILS_PATH)
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_role("status")).to_contain_text("saved")


def test_stalled_patch_times_out_without_automatic_retry(
    page, live_server, isolated_restaurants_path
):
    original = isolated_restaurants_path.read_bytes()
    attempted = []
    page.clock.install()
    page.route(DETAILS_PATH, lambda route: (
        attempted.append(route.request) if route.request.method == "PATCH"
        else route.continue_()
    ))
    open_editor(page, live_server)
    page.get_by_label("Name", exact=True).fill("Unconfirmed")
    with page.expect_request(lambda request: request.method == "PATCH"):
        page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_role("button", name="Save changes")).to_be_disabled()
    page.clock.fast_forward(15_000)
    expect(page.get_by_role("button", name="Save changes")).to_be_enabled()
    expect(page.get_by_role("alert")).to_contain_text("not confirm")
    expect(page.get_by_label("Name", exact=True)).to_have_value("Unconfirmed")
    assert len(attempted) == 1
    assert isolated_restaurants_path.read_bytes() == original


def test_unexpected_success_payload_does_not_claim_save(page, live_server):
    open_editor(page, live_server)
    page.get_by_label("Cuisine", exact=True).fill("Updated")

    def empty_success(route):
        if route.request.method == "PATCH":
            route.fulfill(status=200, content_type="application/json", body="{}")
        else:
            route.continue_()

    page.route(DETAILS_PATH, empty_success)
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_role("alert")).to_contain_text("not confirm")
    expect(page.get_by_label("Cuisine", exact=True)).to_have_value("Updated")


def test_edited_text_is_safe_and_form_fits_phone(page, live_server):
    page.set_viewport_size({"width": 390, "height": 800})
    open_editor(page, live_server)
    page.get_by_label("Name", exact=True).fill("<img src=x onerror=alert(1)>")
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_role("status")).to_contain_text("saved")
    assert page.locator("img").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.page_errors == []
