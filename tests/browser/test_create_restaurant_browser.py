# Exercise Food4Thought's Create restaurant form through the real API and isolated JSON
# persistence.
# It checks creation, validation recovery, storage and network failures, request
# timeouts, duplicate-submit protection, safe text, and keyboard use on a phone
# viewport.

"""Management form behavior through the real API and isolated persistence."""

import json
import os

import pytest

from app.repositories.restaurant import RestaurantRepository

if os.environ.get("REQUIRE_BROWSER_TESTS") != "1":
    pytest.importorskip("playwright.sync_api")

from playwright.sync_api import expect  # noqa: E402


def open_form(page, live_server):
    page.goto(f"{live_server}/app/create-restaurant.html")
    expect(page.get_by_role("heading", name="Create restaurant", exact=True)).to_be_visible(
        timeout=1000
    )


def fill_form(page, name="New Cafe", cuisine="Cafe", description="Fresh food"):
    page.get_by_label("Name", exact=True).fill(name)
    page.get_by_label("Cuisine", exact=True).fill(cuisine)
    page.get_by_label("Description", exact=True).fill(description)


def submit(page):
    page.get_by_role("button", name="Create restaurant", exact=True).click()


def test_customer_page_links_to_management_and_back(page, live_server):
    page.goto(f"{live_server}/app/")
    link = page.get_by_role("link", name="Create restaurant", exact=True)
    expect(link).to_be_visible(timeout=1000)
    link.click()
    expect(page.get_by_label("Name", exact=True)).to_be_visible()
    page.get_by_role("link", name="Browse restaurants", exact=True).click()
    expect(page.locator("#restaurant-list button")).to_have_count(2)


def test_creation_persists_and_links_to_saved_restaurant(page, live_server, isolated_restaurants_path):
    original = RestaurantRepository(isolated_restaurants_path).load_records()
    open_form(page, live_server)
    fill_form(page, name="  New Cafe  ")
    with page.expect_response(lambda response: response.request.method == "POST") as response:
        submit(page)
    assert response.value.status == 201
    assert response.value.request.post_data_json == {
        "name": "  New Cafe  ", "cuisine": "Cafe", "description": "Fresh food"
    }
    saved = response.value.json()
    expect(page.get_by_role("status")).to_contain_text("New Cafe")
    expect(page.get_by_label("Name", exact=True)).to_have_value("")
    records = RestaurantRepository(isolated_restaurants_path).load_records()
    assert records[:-1] == original
    assert records[-1].id == saved["id"]
    assert records[-1].name == "New Cafe"
    assert records[-1].menu_items == []
    page.get_by_role("link", name="View restaurant", exact=True).click()
    expect(page.locator("#details-name")).to_have_text("New Cafe")
    assert page.page_errors == []


def test_empty_required_field_blocks_submission(page, live_server, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    requests = []
    page.on("request", lambda request: requests.append(request) if request.method == "POST" else None)
    open_form(page, live_server)
    fill_form(page, name="")
    submit(page)
    expect(page.get_by_label("Name", exact=True)).to_be_focused()
    assert page.get_by_label("Name", exact=True).evaluate("el => el.validity.valueMissing")
    assert requests == []
    assert isolated_restaurants_path.read_bytes() == before


def test_backend_validation_identifies_fields_and_allows_correction(page, live_server, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    open_form(page, live_server)
    fill_form(page, name="   ", cuisine="   ", description="   ")
    with page.expect_response(lambda response: response.request.method == "POST") as response:
        submit(page)
    assert response.value.status == 422
    expect(page.get_by_role("alert")).to_contain_text("Name")
    expect(page.get_by_role("alert")).to_contain_text("Cuisine")
    expect(page.get_by_role("alert")).to_contain_text("Description")
    for field in ("Name", "Cuisine", "Description"):
        expect(page.get_by_label(field, exact=True)).to_have_attribute("aria-invalid", "true")
        expect(page.get_by_label(field, exact=True)).to_have_value("   ")
    expect(page.get_by_label("Name", exact=True)).to_be_focused()
    assert isolated_restaurants_path.read_bytes() == before
    fill_form(page)
    submit(page)
    expect(page.get_by_role("status")).to_contain_text("New Cafe")
    expect(page.get_by_role("alert", include_hidden=True)).to_be_empty()
    expect(page.locator('[aria-invalid="true"]')).to_have_count(0)


def test_storage_failure_preserves_input_and_can_be_retried(page, live_server, isolated_restaurants_path):
    original = isolated_restaurants_path.read_bytes()
    isolated_restaurants_path.write_text("broken JSON", encoding="utf-8")
    open_form(page, live_server)
    fill_form(page)
    submit(page)
    expect(page.get_by_role("alert")).to_contain_text("Restaurant data is unavailable")
    expect(page.get_by_label("Name", exact=True)).to_have_value("New Cafe")
    expect(page.get_by_role("link", name="View restaurant", exact=True)).to_be_hidden()
    assert isolated_restaurants_path.read_text(encoding="utf-8") == "broken JSON"
    isolated_restaurants_path.write_bytes(original)
    submit(page)
    expect(page.get_by_role("status")).to_contain_text("New Cafe")
    assert len(RestaurantRepository(isolated_restaurants_path).load_records()) == 3


def test_corrected_field_errors_clear_before_resubmission(page, live_server, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    open_form(page, live_server)
    fill_form(page, name="   ", cuisine="   ", description="   ")
    submit(page)
    expect(page.locator('[aria-invalid="true"]')).to_have_count(3)

    # Another blank value has not corrected the backend's nonblank requirement.
    page.get_by_label("Name", exact=True).fill(" ")
    expect(page.get_by_label("Name", exact=True)).to_have_attribute("aria-invalid", "true")
    for label, value, remaining in [("Name", "New Cafe", 2), ("Cuisine", "Cafe", 1),
                                    ("Description", "Fresh food", 0)]:
        field = page.get_by_label(label, exact=True)
        error_id = field.get_attribute("aria-describedby")
        assert error_id
        field.fill(value)
        expect(field).not_to_have_attribute("aria-invalid", "true")
        assert field.get_attribute("aria-describedby") is None
        expect(page.locator(f"#{error_id}")).to_have_count(0)
        expect(page.locator('[aria-invalid="true"]')).to_have_count(remaining)
        expect(page.locator("#create-errors li")).to_have_count(remaining)
    expect(page.get_by_role("alert", include_hidden=True)).to_be_empty()
    assert isolated_restaurants_path.read_bytes() == before
    assert page.page_errors == []


def test_stalled_post_times_out_without_retrying(page, live_server, isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    requests = []
    page.clock.install()
    page.route("**/restaurants", lambda route: requests.append(route.request))
    open_form(page, live_server)
    fill_form(page)
    with page.expect_request(lambda request: request.method == "POST"):
        submit(page)
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_disabled()
    page.clock.fast_forward(15_000)
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_enabled()
    expect(page.get_by_label("Name", exact=True)).to_be_enabled()
    expect(page.get_by_label("Name", exact=True)).to_have_value("New Cafe")
    expect(page.get_by_label("Cuisine", exact=True)).to_have_value("Cafe")
    expect(page.get_by_label("Description", exact=True)).to_have_value("Fresh food")
    expect(page.get_by_role("alert")).to_contain_text("Check the restaurant list")
    expect(page.get_by_role("status", include_hidden=True)).to_be_empty()
    expect(page.locator("form")).not_to_have_attribute("aria-busy", "true")
    expect(page.get_by_role("link", name="View restaurant", exact=True)).to_be_hidden()
    page.clock.fast_forward(30_000)
    assert len(requests) == 1
    assert isolated_restaurants_path.read_bytes() == before
    page.unroute("**/restaurants")
    submit(page)
    expect(page.get_by_role("status")).to_contain_text("New Cafe")
    assert len(RestaurantRepository(isolated_restaurants_path).load_records()) == 3
    assert page.page_errors == []


def test_lost_response_does_not_retry_a_possibly_saved_creation(page, live_server, isolated_restaurants_path):
    attempts = []

    def lose_response(route):
        attempts.append(route.request)
        route.fetch()  # The server saves, but the browser never receives confirmation.
        route.abort()

    page.route("**/restaurants", lose_response)
    open_form(page, live_server)
    fill_form(page)
    submit(page)
    expect(page.get_by_role("alert")).to_contain_text("Check the restaurant list")
    expect(page.get_by_label("Name", exact=True)).to_have_value("New Cafe")
    expect(page.get_by_role("link", name="View restaurant", exact=True)).to_be_hidden()
    page.wait_for_timeout(200)
    assert len(attempts) == 1
    assert len(RestaurantRepository(isolated_restaurants_path).load_records()) == 3
    assert page.page_errors == []


@pytest.mark.parametrize("status,body,expected", [
    (503, "<h1>Unavailable</h1>", "HTTP 503"),
    (201, json.dumps({"unexpected": True}), "Check the restaurant list"),
])
def test_unexpected_responses_show_feedback_without_clearing_input(page, live_server, status, body, expected):
    page.route("**/restaurants", lambda route: route.fulfill(status=status, body=body))
    open_form(page, live_server)
    fill_form(page)
    submit(page)
    expect(page.get_by_role("alert")).to_contain_text(expected)
    expect(page.get_by_label("Description", exact=True)).to_have_value("Fresh food")
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_enabled()
    expect(page.get_by_role("link", name="View restaurant", exact=True)).to_be_hidden()
    assert page.page_errors == []


def test_pending_submission_prevents_duplicate_posts(page, live_server, isolated_restaurants_path):
    held = []
    page.route("**/restaurants", lambda route: held.append(route))
    open_form(page, live_server)
    fill_form(page)
    submit(page)
    expect(page.get_by_role("status")).to_contain_text("Creating")
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_disabled()
    expect(page.get_by_label("Name", exact=True)).to_be_disabled()
    page.locator("form").evaluate("form => form.dispatchEvent(new Event('submit', {cancelable: true}))")
    page.wait_for_timeout(200)
    assert len(held) == 1
    held[0].continue_()
    expect(page.get_by_role("status")).to_contain_text("New Cafe")
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_enabled()
    assert len(RestaurantRepository(isolated_restaurants_path).load_records()) == 3


def test_api_text_is_safe_and_form_works_by_keyboard_on_phone(page, live_server):
    page.set_viewport_size({"width": 390, "height": 844})
    open_form(page, live_server)
    name = '<img src=x onerror="window.injected=true">' + "店" * 100
    page.get_by_label("Name", exact=True).focus()
    page.keyboard.insert_text(name)
    page.keyboard.press("Tab")
    page.keyboard.insert_text("Cafe")
    page.keyboard.press("Tab")
    page.keyboard.insert_text("Fresh food")
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Create restaurant", exact=True)).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_role("status")).to_contain_text(name)
    assert page.locator("img").count() == 0
    assert page.evaluate("window.injected") is None
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.page_errors == []
