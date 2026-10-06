from typing import Annotated

from fastapi import FastAPI, Path
from fastapi.testclient import TestClient

from app.api.openapi import (
    CONTRACT_NO_VALIDATION_ERROR_OPERATIONS,
    install_openapi,
    remove_validation_errors,
)


def _schema_with_path_only_gets(*paths):
    return {
        "paths": {
            path: {
                "get": {
                    "parameters": [{"in": "path"}],
                    "responses": {"200": {}, "422": {"description": "Validation Error"}},
                }
            }
            for path in paths
        }
    }


def test_removes_422_only_from_listed_operations():
    schema = _schema_with_path_only_gets("/listed/{id}", "/unlisted/{id}")

    remove_validation_errors(schema, {("get", "/listed/{id}")})

    assert "422" not in schema["paths"]["/listed/{id}"]["get"]["responses"]
    assert "422" in schema["paths"]["/unlisted/{id}"]["get"]["responses"]


def test_ignores_listed_operations_missing_from_schema():
    schema = _schema_with_path_only_gets("/present/{id}")

    remove_validation_errors(schema, {("get", "/absent/{id}")})

    assert "422" in schema["paths"]["/present/{id}"]["get"]["responses"]


def test_contract_list_names_the_menu_operation():
    assert ("get", "/restaurants/{restaurant_id}/menu") in (
        CONTRACT_NO_VALIDATION_ERROR_OPERATIONS
    )


def test_validated_path_only_get_keeps_422():
    # Regression: an int path parameter can fail validation, so its 422 must stay.
    app = FastAPI()

    @app.get("/things/{thing_id}")
    def get_thing(thing_id: Annotated[int, Path()]) -> dict[str, int]:
        return {"thing_id": thing_id}

    install_openapi(app)
    client = TestClient(app)

    responses = client.get("/openapi.json").json()["paths"]["/things/{thing_id}"]["get"][
        "responses"
    ]
    assert "422" in responses
    assert client.get("/things/not-a-number").status_code == 422
