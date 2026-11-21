"""Audit the live Food4Thought OpenAPI against the M1 and M2 route contracts.
The TestClient reads /docs and /openapi.json from the real application; isolated
store fixtures let representative errors be exercised without touching seed data.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_now
from app.main import app


# All public HTTP operations, including the retained eight-operation M1 slice.
# Each set is the *documented* status inventory, not a promise that every
# status happens on every request. Tests below also exercise representative cases.
OPERATIONS = {
    ("get", "/health"): {200},
    ("get", "/restaurants"): {200, 422, 500},
    ("post", "/restaurants"): {201, 401, 403, 422, 500},
    ("get", "/restaurants/{restaurant_id}"): {200, 404, 500},
    ("patch", "/restaurants/{restaurant_id}"): {200, 401, 403, 404, 422, 500},
    ("get", "/restaurants/{restaurant_id}/menu"): {200, 404, 500},
    ("post", "/restaurants/{restaurant_id}/menu/items"): {201, 401, 403, 404, 422, 500},
    ("patch", "/restaurants/{restaurant_id}/menu/items/{item_id}"): {
        200, 401, 403, 404, 422, 500
    },
    ("post", "/customers"): {201, 409, 422, 500},
    ("post", "/auth/login"): {200, 401, 422, 500},
    ("get", "/customers/me"): {200, 401, 403, 500},
    ("patch", "/customers/me"): {200, 401, 403, 422, 500},
    ("post", "/customers/me/deactivate"): {200, 401, 403, 500},
    ("put", "/customers/me/cart"): {200, 201, 401, 403, 404, 409, 500},
    ("get", "/customers/me/cart"): {200, 401, 403, 404, 409, 500},
    ("post", "/customers/me/cart/items"): {200, 401, 403, 404, 409, 422, 500},
    ("patch", "/customers/me/cart/items/{item_id}"): {200, 401, 403, 404, 409, 422, 500},
    ("delete", "/customers/me/cart/items/{item_id}"): {200, 401, 403, 404, 409, 500},
    ("delete", "/customers/me/cart/items"): {200, 401, 403, 404, 409, 500},
    ("post", "/customers/me/checkout"): {200, 201, 401, 403, 404, 409, 422, 500},
    ("get", "/customers/me/orders"): {200, 401, 403, 500},
    ("get", "/customers/me/orders/{order_id}"): {200, 401, 403, 404, 500},
}

BODY_MODELS = {
    ("post", "/restaurants"): "RestaurantCreate",
    ("patch", "/restaurants/{restaurant_id}"): "RestaurantUpdate",
    ("post", "/restaurants/{restaurant_id}/menu/items"): "MenuItemCreate",
    ("patch", "/restaurants/{restaurant_id}/menu/items/{item_id}"): "MenuItemUpdate",
    ("post", "/customers"): "CustomerRegistration",
    ("post", "/auth/login"): "LoginRequest",
    ("patch", "/customers/me"): "CustomerProfileUpdate",
    ("post", "/customers/me/cart/items"): "AddCartItemRequest",
    ("patch", "/customers/me/cart/items/{item_id}"): "UpdateCartQuantityRequest",
    ("post", "/customers/me/checkout"): "CheckoutRequest",
}

# Return models, including the separately documented existing/new cart and
# checkout statuses. Collection responses are covered in their own assertions.
SUCCESS_MODELS = {
    ("post", "/restaurants"): {201: "Restaurant"},
    ("get", "/restaurants/{restaurant_id}"): {200: "Restaurant"},
    ("patch", "/restaurants/{restaurant_id}"): {200: "Restaurant"},
    ("get", "/restaurants/{restaurant_id}/menu"): {200: "Menu"},
    ("post", "/restaurants/{restaurant_id}/menu/items"): {201: "MenuItem"},
    ("patch", "/restaurants/{restaurant_id}/menu/items/{item_id}"): {200: "MenuItem"},
    ("post", "/customers"): {201: "Customer"},
    ("post", "/auth/login"): {200: "LoginResponse"},
    ("get", "/customers/me"): {200: "Customer"},
    ("patch", "/customers/me"): {200: "Customer"},
    ("post", "/customers/me/deactivate"): {200: "Customer"},
    ("put", "/customers/me/cart"): {200: "CartView", 201: "CartView"},
    ("get", "/customers/me/cart"): {200: "CartView"},
    ("post", "/customers/me/cart/items"): {200: "CartView"},
    ("patch", "/customers/me/cart/items/{item_id}"): {200: "CartView"},
    ("delete", "/customers/me/cart/items/{item_id}"): {200: "CartView"},
    ("delete", "/customers/me/cart/items"): {200: "CartView"},
    ("post", "/customers/me/checkout"): {200: "CheckoutResponse", 201: "CheckoutResponse"},
    ("get", "/customers/me/orders/{order_id}"): {200: "Order"},
}

PUBLIC = {
    ("get", "/health"),
    ("get", "/restaurants"),
    ("get", "/restaurants/{restaurant_id}"),
    ("get", "/restaurants/{restaurant_id}/menu"),
    ("post", "/customers"),
    ("post", "/auth/login"),
}


@pytest.fixture
def client(auth_accounts, monkeypatch):
    # Every request uses a token backed by the disposable session and account stores.
    monkeypatch.setitem(app.dependency_overrides, get_now, lambda: auth_accounts.now)
    with TestClient(app, raise_server_exceptions=False) as api:
        yield api


@pytest.fixture
def schema(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    return response.json()


def _operation(schema, key):
    method, path = key
    return schema["paths"][path][method]


def _response_schema(operation, status):
    return operation["responses"][str(status)]["content"]["application/json"]["schema"]


def test_swagger_ui_serves_the_same_live_schema(client, schema):
    page = client.get("/docs")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "swagger-ui" in page.text.lower()
    assert "/openapi.json" in page.text
    assert schema["info"]["title"] == "Food4Thought API"


def test_entire_operation_inventory_and_documented_statuses(schema):
    published = {
        (method, path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert published == set(OPERATIONS)

    for key, statuses in OPERATIONS.items():
        operation = _operation(schema, key)
        assert operation.get("summary")
        assert operation.get("description")
        assert set(operation["responses"]) == {str(status) for status in statuses}, key


def test_request_models_and_path_query_parameters(schema):
    for key in OPERATIONS:
        operation = _operation(schema, key)
        request_body = operation.get("requestBody")
        if key in BODY_MODELS:
            assert request_body["required"] is True, key
            model = BODY_MODELS[key]
            assert request_body["content"]["application/json"]["schema"]["$ref"] == (
                f"#/components/schemas/{model}"
            )
        else:
            assert request_body is None, key

        path = key[1]
        expected_path_names = {
            part[1:-1] for part in path.split("/") if part.startswith("{") and part.endswith("}")
        }
        parameters = operation.get("parameters", [])
        actual_path_names = {p["name"] for p in parameters if p["in"] == "path"}
        assert actual_path_names == expected_path_names, key
        assert all(p["required"] for p in parameters if p["in"] == "path"), key

        query_names = {p["name"] for p in parameters if p["in"] == "query"}
        assert query_names == ({"cuisine"} if key == ("get", "/restaurants") else set()), key


def test_response_shapes_include_m1_and_m2_models(schema):
    for key, expected in SUCCESS_MODELS.items():
        for status, model in expected.items():
            assert _response_schema(_operation(schema, key), status)["$ref"] == (
                f"#/components/schemas/{model}"
            ), (key, status)

    for key, model in [
        (("get", "/restaurants"), "Restaurant"),
        (("get", "/customers/me/orders"), "Order"),
    ]:
        body = _response_schema(_operation(schema, key), 200)
        assert body["type"] == "array"
        assert body["items"]["$ref"] == f"#/components/schemas/{model}"

    for key, statuses in OPERATIONS.items():
        operation = _operation(schema, key)
        for status in statuses - {200, 201, 422}:
            body = _response_schema(operation, status)
            assert body["$ref"] == "#/components/schemas/ErrorResponse", (key, status)


def test_bearer_auth_is_declared_only_on_protected_operations(schema):
    scheme = schema["components"]["securitySchemes"]["HTTPBearer"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    for key in OPERATIONS:
        expected = None if key in PUBLIC else [{"HTTPBearer": []}]
        assert _operation(schema, key).get("security") == expected, key


def test_validation_responses_are_not_removed_from_real_input_boundaries(schema):
    for key, statuses in OPERATIONS.items():
        responses = _operation(schema, key)["responses"]
        assert ("422" in responses) == (422 in statuses), key

    # These opaque string-only reads and deletion have no user-value validation.
    for key in [
        ("get", "/restaurants/{restaurant_id}"),
        ("get", "/restaurants/{restaurant_id}/menu"),
        ("get", "/customers/me/orders/{order_id}"),
        ("delete", "/customers/me/cart/items/{item_id}"),
    ]:
        assert "422" not in _operation(schema, key)["responses"]


def test_public_schema_excludes_storage_records_and_protects_examples(schema):
    models = schema["components"]["schemas"]
    assert {"Customer", "CartView", "Order", "CheckoutResponse"} <= set(models)
    assert not {"StoredCustomer", "SessionRecord", "CartRecord", "RestaurantRecord"} & set(models)
    assert not {"password", "password_hash", "role"} & set(models["Customer"]["properties"])
    assert not {"customer_id", "unit_price", "total"} & set(
        models["AddCartItemRequest"]["properties"]
    )
    assert models["CartView"]["properties"]["total"]["pattern"].endswith(r"\.[0-9]{2}$")
    assert models["Order"]["properties"]["status"]["const"] == "placed"
    assert models["MenuItem"]["properties"]["available"]["type"] == "boolean"

    examples = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/examples/m2.json").read_text(
            encoding="utf-8"
        )
    )
    assert examples["login_request"]["password"].startswith("example-only-")
    assert examples["login_response"]["access_token"].startswith("example-token-")
    assert examples["cart"]["total"] == "39.00"
    assert examples["checkout_response"]["order"]["total"] == "39.00"
    assert examples["checkout_response"]["order"]["status"] == "placed"
    # Example dummy secrets are in the separate example bundle, never in /openapi.json.
    assert examples["login_request"]["password"] not in json.dumps(schema)
    assert examples["login_response"]["access_token"] not in json.dumps(schema)


def test_representative_422_404_403_409_and_500_are_real_http_results(
    client, auth_accounts, m2_store_paths
):
    customer = auth_accounts.headers("customer_a")
    manager = auth_accounts.headers("restaurant_user")
    admin = auth_accounts.headers("administrator")

    for method, path, headers, payload in [
        ("get", "/restaurants?cuisine=%20", {}, None),
        ("post", "/customers", {}, {"name": ""}),
        ("post", "/auth/login", {}, {"email": "missing@example.invalid"}),
        ("post", "/restaurants", admin, {"name": ""}),
        ("patch", "/customers/me", customer, {}),
        ("post", "/customers/me/cart/items", customer, {"quantity": 0}),
        ("post", "/customers/me/checkout", customer, {"cart_id": "c", "cart_revision": -1}),
    ]:
        response = client.request(method, path, headers=headers, json=payload)
        assert response.status_code == 422, (method, path, response.text)
        assert isinstance(response.json()["detail"], list), (method, path)

    assert client.get("/restaurants/does-not-exist").status_code == 404
    assert client.get("/customers/me/orders/does-not-exist", headers=customer).status_code == 404

    no_token = client.get("/customers/me/orders")
    assert no_token.status_code == 401
    assert no_token.headers["www-authenticate"] == "Bearer"
    assert client.get("/customers/me/orders", headers=manager).status_code == 403
    assert client.post("/restaurants", headers=customer, json={"name": "X"}).status_code == 403

    created = client.put("/customers/me/cart", headers=customer)
    assert created.status_code == 201
    empty = created.json()
    conflict = client.post(
        "/customers/me/checkout", headers=customer,
        json={"cart_id": empty["id"], "cart_revision": empty["revision"]},
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Cart is empty"}

    # A corrupt disposable order store is a storage error, not an empty history.
    m2_store_paths["orders"].write_text("{invalid-json", encoding="utf-8")
    bad_storage = client.get("/customers/me/orders", headers=customer)
    assert bad_storage.status_code == 500
    assert bad_storage.json() == {"detail": "Order data is unavailable"}
