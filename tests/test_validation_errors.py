import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize(
    ("path", "valid_body", "field"),
    [
        (
            "/restaurants",
            {"name": "Cafe", "cuisine": "Cafe", "description": "Fresh food"},
            "name",
        ),
        (
            "/restaurants/restaurant-001/menu/items",
            {"name": "Soup", "description": "Hot soup", "price": "4.50"},
            "price",
        ),
    ],
)
@pytest.mark.parametrize("raw_value", ["1e309", "NaN", "Infinity", "-Infinity", '"\\ud800"'])
def test_invalid_values_return_serializable_422_without_writing(
    isolated_restaurants_path, path, valid_body, field, raw_value
):
    # Send raw JSON: encoding through the client's json= parameter can reject
    # non-finite numbers before the request reaches the application.
    remaining_fields = {key: value for key, value in valid_body.items() if key != field}
    body = json.dumps(remaining_fields)[:-1] + f', "{field}": {raw_value}' + "}"
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app, raise_server_exceptions=False).post(
        path, content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert response.content.decode("utf-8")
    detail = json.loads(response.content, parse_constant=_reject_nonfinite)["detail"]
    assert detail[0]["loc"] == ["body", field]
    assert detail[0]["type"]
    assert detail[0]["msg"]
    assert isinstance(detail[0]["input"], str)
    assert isolated_restaurants_path.read_bytes() == before


def _reject_nonfinite(value):
    raise AssertionError(f"Response contains a non-JSON number: {value}")


def test_invalid_nested_extra_field_returns_serializable_error(isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()
    body = (
        '{"name":"Soup","description":"Hot","price":"1.00",'
        '"extra":{"nested":[NaN,Infinity,{"\\udfff":"\\ud800"}]}}'
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/restaurants/restaurant-001/menu/items",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    detail = json.loads(response.content, parse_constant=_reject_nonfinite)["detail"]
    assert detail[0]["type"] == "extra_forbidden"
    assert detail[0]["loc"] == ["body", "extra"]
    assert detail[0]["input"] == {
        "nested": ["nan", "inf", {"\udfff": "\ud800"}]
    }
    assert isolated_restaurants_path.read_bytes() == before


def test_ordinary_validation_error_keeps_diagnostic_fields(isolated_restaurants_path):
    before = isolated_restaurants_path.read_bytes()

    response = TestClient(app).post(
        "/restaurants/restaurant-001/menu/items",
        json={"name": "Soup", "description": "Hot", "price": 4.5},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [{
            "type": "string_type",
            "loc": ["body", "price"],
            "msg": "Input should be a valid string",
            "input": 4.5,
        }]
    }
    assert isolated_restaurants_path.read_bytes() == before


def test_invalid_body_still_precedes_storage_failure(isolated_restaurants_path):
    isolated_restaurants_path.unlink()

    response = TestClient(app, raise_server_exceptions=False).post(
        "/restaurants/unknown/menu/items",
        content='{"name":"Soup","description":"Hot","price":1e309}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "price"]
    assert not isolated_restaurants_path.exists()


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
