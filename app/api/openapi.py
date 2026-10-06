from collections.abc import Collection
from typing import Any

from fastapi import FastAPI

# Operations the M1 contract defines as having no 422: their only input is an
# opaque, non-empty string path segment, so request validation cannot fail.
# Add an operation here only when the contract says so; any other operation,
# including a GET with a validated path parameter, keeps FastAPI's 422.
CONTRACT_NO_VALIDATION_ERROR_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("get", "/restaurants/{restaurant_id}/menu"),
    }
)


def remove_validation_errors(
    schema: dict[str, Any], operations: Collection[tuple[str, str]]
) -> dict[str, Any]:
    """Remove the automatic 422 response from each listed (method, path) operation."""
    for method, path in operations:
        operation = schema.get("paths", {}).get(path, {}).get(method)
        if operation is not None:
            operation.get("responses", {}).pop("422", None)
    return schema


def install_openapi(
    app: FastAPI,
    operations: Collection[tuple[str, str]] = CONTRACT_NO_VALIDATION_ERROR_OPERATIONS,
) -> None:
    """Post-process the generated schema once, when FastAPI first builds it."""
    generate_default_schema = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            remove_validation_errors(generate_default_schema(), operations)
        return app.openapi_schema

    app.openapi = openapi
