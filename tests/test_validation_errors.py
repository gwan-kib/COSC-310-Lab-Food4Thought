import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize(
    "method, path",
    [("patch", "/restaurants/restaurant-001"), ("post", "/restaurants")],
)
@pytest.mark.parametrize(
    "fields, invalid_field, error_type",
    [
        ('"name":1e400', "name", "string_type"),
        ('"name":-1e400', "name", "string_type"),
        (r'"name":"\ud800"', "name", "string_unicode"),
        ('"name":"Valid","extra":{"nested":[1e400]}', "extra", "extra_forbidden"),
        (r'"name":"Valid","extra":{"nested":"\ud800"}', "extra", "extra_forbidden"),
    ],
)
def test_invalid_input_always_has_serializable_validation_response(
    isolated_restaurants_path, method, path, fields, invalid_field, error_type
):
    original = isolated_restaurants_path.read_bytes()
    body = '{' + fields + ',"cuisine":"Cafe","description":"Food"}'

    response = TestClient(app, raise_server_exceptions=False).request(
        method, path, content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"

    def reject_nonfinite(value):
        raise AssertionError(f"Response contains non-JSON number: {value}")

    errors = json.loads(response.content.decode("utf-8"), parse_constant=reject_nonfinite)
    # Union validation may append a branch name after the field location.
    assert errors["detail"][0]["loc"][:2] == ["body", invalid_field]
    assert errors["detail"][0]["type"] == error_type
    assert errors["detail"][0]["msg"]
    assert isolated_restaurants_path.read_bytes() == original


@pytest.mark.parametrize(
    "method, path",
    [("patch", "/restaurants/restaurant-001"), ("post", "/restaurants")],
)
def test_non_json_invalid_utf8_body_returns_validation_error(
    isolated_restaurants_path, method, path
):
    original = isolated_restaurants_path.read_bytes()

    response = TestClient(app, raise_server_exceptions=False).request(
        method, path, content=b"\xff\xfe", headers={"Content-Type": "text/plain"}
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body"]
    assert error["type"] == "model_attributes_type"
    assert isolated_restaurants_path.read_bytes() == original
