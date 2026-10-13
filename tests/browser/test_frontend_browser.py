"""Exercise Food4Thought's customer discovery page in Chromium against the real API and
isolated storage. Regression scenarios from PR #58 review protect selection races,
malformed links, retries, independent menu errors, and long-text layout at phone
widths.
"""

import json
import os

import pytest

# Skip cleanly where Playwright isn't installed; CI requires it and fails instead.
if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip(
        "playwright.sync_api",
        reason="Playwright is not installed (pip install -r requirements-dev.txt)",
    )

from playwright.sync_api import expect  # noqa: E402

CEDAR_BOWL_DETAILS = "**/restaurants/restaurant-001"
CEDAR_BOWL_MENU = "**/restaurants/restaurant-001/menu"


def _restaurant_buttons(page):
    return page.locator("#restaurant-list button.restaurant")


def _wait_until(page, condition, description, timeout_ms=5000):
    """Poll the page until condition() is true, failing clearly instead of hanging."""
    waited = 0
    while not condition():
        assert waited < timeout_ms, f"Timed out after {timeout_ms} ms waiting for {description}"
        page.wait_for_timeout(20)
        waited += 20


def _fail_with_500(route):
    route.fulfill(
        status=500,
        content_type="application/json",
        body=json.dumps({"detail": "Restaurant data is unavailable"}),
    )


def test_list_details_and_menu_load(page, live_server):
    page.goto(f"{live_server}/app/")
    expect(_restaurant_buttons(page)).to_have_count(2)

    _restaurant_buttons(page).filter(has_text="Cedar Bowl").click()

    expect(page.locator("#details-name")).to_have_text("Cedar Bowl")
    expect(page.locator("#menu-list li")).to_have_count(2)
    assert page.page_errors == []


def test_clearing_selection_ignores_late_detail_responses(page, live_server):
    # Hold the detail and menu responses until after the selection is cleared.
    held = []

    def hold(route):
        held.append(route)

    page.route(CEDAR_BOWL_DETAILS, hold)
    page.route(CEDAR_BOWL_MENU, hold)
    page.goto(f"{live_server}/app/")
    _restaurant_buttons(page).filter(has_text="Cedar Bowl").click()
    expect(page.locator("#details-status")).to_have_text("Loading restaurant…")
    _wait_until(page, lambda: len(held) == 2, "the details and menu requests to be sent")

    page.go_back()
    expect(page.locator("#details-status")).to_have_text(
        "Select a restaurant to see its details and menu."
    )
    for route in held:
        route.continue_()
    page.wait_for_timeout(300)

    expect(page.locator("#details-content")).to_be_hidden()
    expect(page.locator("#details-status")).to_have_text(
        "Select a restaurant to see its details and menu."
    )


def test_malformed_deep_link_keeps_list_usable(page, live_server):
    page.goto(f"{live_server}/app/#/restaurants/%")

    expect(_restaurant_buttons(page)).to_have_count(2)
    expect(page.locator("#details-status")).to_have_text("That restaurant link isn't valid.")

    _restaurant_buttons(page).filter(has_text="Harbour Slice").click()
    expect(page.locator("#details-name")).to_have_text("Harbour Slice")
    assert page.page_errors == []


def test_same_restaurant_can_be_retried_after_an_error(page, live_server):
    page.route(CEDAR_BOWL_DETAILS, _fail_with_500)
    page.goto(f"{live_server}/app/")
    cedar_bowl = _restaurant_buttons(page).filter(has_text="Cedar Bowl")
    cedar_bowl.click()
    expect(page.locator("#details-status")).to_contain_text("Could not load restaurant")

    page.unroute(CEDAR_BOWL_DETAILS)
    cedar_bowl.click()

    expect(page.locator("#details-name")).to_have_text("Cedar Bowl")
    expect(page.locator("#details-content")).to_be_visible()


def test_long_api_text_stays_within_a_phone_viewport(page, live_server, isolated_restaurants_path):
    long_word = "LongName" * 12
    record = {
        "id": "long",
        "name": long_word,
        "cuisine": "Cuisine" * 10,
        "description": "Description" * 10,
        "menu_items": [
            {"id": "i", "name": "Dish" * 25, "description": "Words" * 25, "price": "999.00"}
        ],
    }
    isolated_restaurants_path.write_text(json.dumps([record]), encoding="utf-8")
    page.set_viewport_size({"width": 390, "height": 800})

    page.goto(f"{live_server}/app/#/restaurants/long")
    expect(page.locator("#details-name")).to_have_text(long_word)

    document_width = page.evaluate("document.documentElement.scrollWidth")
    assert document_width <= 390
    for selector in ("#cuisine-input", "#filter-form button[type=submit]", ".price"):
        box = page.locator(selector).first.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 390, selector


def test_details_still_show_when_only_the_menu_fails(page, live_server):
    page.route(CEDAR_BOWL_MENU, _fail_with_500)
    page.goto(f"{live_server}/app/")
    cedar_bowl = _restaurant_buttons(page).filter(has_text="Cedar Bowl")
    cedar_bowl.click()

    # Restaurant details are the M1 requirement, so they must survive a menu error.
    expect(page.locator("#details-content")).to_be_visible()
    expect(page.locator("#details-name")).to_have_text("Cedar Bowl")
    expect(page.locator("#details-cuisine")).to_have_text("Japanese")
    expect(page.locator("#menu-status")).to_have_text(
        "Could not load the menu: Restaurant data is unavailable"
    )
    expect(page.locator("#menu-list li")).to_have_count(0)

    # Clicking the restaurant again retries the menu once it is available.
    page.unroute(CEDAR_BOWL_MENU)
    cedar_bowl.click()
    expect(page.locator("#menu-list li")).to_have_count(2)
    expect(page.locator("#menu-status")).to_be_hidden()
    assert page.page_errors == []
