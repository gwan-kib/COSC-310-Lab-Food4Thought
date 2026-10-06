from app.api.openapi import remove_unreachable_validation_errors


def _operation(parameters, *, with_body=False):
    operation = {
        "parameters": parameters,
        "responses": {"200": {}, "422": {"description": "Validation Error"}},
    }
    if with_body:
        operation["requestBody"] = {"content": {}}
    return operation


def test_drops_422_from_get_with_only_path_parameters():
    schema = {"paths": {"/items/{item_id}": {"get": _operation([{"in": "path"}])}}}

    remove_unreachable_validation_errors(schema)

    assert "422" not in schema["paths"]["/items/{item_id}"]["get"]["responses"]


def test_keeps_422_when_get_has_query_parameter():
    schema = {
        "paths": {"/items": {"get": _operation([{"in": "query"}])}},
    }

    remove_unreachable_validation_errors(schema)

    assert "422" in schema["paths"]["/items"]["get"]["responses"]


def test_keeps_422_on_operations_with_request_bodies():
    schema = {
        "paths": {
            "/items/{item_id}": {
                "patch": _operation([{"in": "path"}], with_body=True),
            }
        }
    }

    remove_unreachable_validation_errors(schema)

    assert "422" in schema["paths"]["/items/{item_id}"]["patch"]["responses"]
