# Check that Food4Thought serves its customer page and shared assets through the backend
# application.
# It also verifies the redirect, static-directory resolution, API-only data access, and
# source safeguards for rendering restaurant text.

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import FRONTEND_DIR, app

ROOT = Path(__file__).resolve().parents[1]
COMMITTED_DATA = ROOT / "data" / "restaurants.json"


def test_frontend_page_is_served_at_app():
    response = TestClient(app).get("/app/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="restaurant-list"' in response.text
    assert 'id="restaurant-details"' in response.text
    assert 'src="app.js"' in response.text


def test_frontend_assets_are_served():
    client = TestClient(app)

    script = client.get("/app/app.js")
    styles = client.get("/app/styles.css")

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert styles.status_code == 200
    assert styles.headers["content-type"].startswith("text/css")


def test_root_redirects_to_frontend():
    response = TestClient(app).get("/", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/app/"


def test_frontend_routes_stay_out_of_api_docs():
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/" not in paths
    assert not any(path.startswith("/app") for path in paths)


def test_frontend_directory_does_not_depend_on_working_directory():
    assert FRONTEND_DIR.is_absolute()
    assert (FRONTEND_DIR / "index.html").is_file()


def test_frontend_reads_data_through_the_rest_api():
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    assert "fetch(" in script
    assert "/restaurants" in script
    assert "/menu" in script
    assert "restaurants.json" not in script


def test_frontend_has_no_hard_coded_restaurant_data():
    records = json.loads(COMMITTED_DATA.read_text(encoding="utf-8"))
    values = {record[field] for record in records for field in ("id", "name")}
    values |= {item["name"] for record in records for item in record.get("menu_items", [])}
    sources = "".join(
        path.read_text(encoding="utf-8") for path in FRONTEND_DIR.iterdir() if path.is_file()
    )

    assert not [value for value in values if value in sources]


def test_frontend_renders_api_text_without_html_injection():
    # Restaurants can be created through the API, so their text must be rendered
    # as text, never parsed as HTML.
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "textContent" in script
