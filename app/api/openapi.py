from typing import Any

from fastapi import FastAPI


def remove_unreachable_validation_errors(schema: dict[str, Any]) -> dict[str, Any]:
    """Drop FastAPI's automatic 422 from GET operations whose only input is a path.

    Such operations take an opaque, non-empty path segment with no query or body,
    so request validation cannot fail; the M1 contract documents only 404/500.
    """
    for path_item in schema.get("paths", {}).values():
        operation = path_item.get("get")
        if operation is None:
            continue
        parameters = operation.get("parameters", [])
        if parameters and all(parameter["in"] == "path" for parameter in parameters):
            operation["responses"].pop("422", None)
    return schema


def install_openapi(app: FastAPI) -> None:
    """Post-process the generated schema once, when FastAPI first builds it."""
    generate_default_schema = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            remove_unreachable_validation_errors(generate_default_schema())
        return app.openapi_schema

    app.openapi = openapi
