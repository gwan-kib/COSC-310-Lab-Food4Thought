# Serialize Food4Thought's request-validation failures as JSON while preserving
# useful field diagnostics. Safely encode rejected non-finite numbers, Unicode, and
# bytes, and redact submitted passwords so a 422 never echoes credentials.

import json
import math
from typing import Any

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

# Compared case-insensitively against field names and error locations.
SENSITIVE_FIELDS = frozenset({"password"})
REDACTED = "[redacted]"


def _is_sensitive(name: object) -> bool:
    return isinstance(name, str) and name.casefold() in SENSITIVE_FIELDS


def _redact(value: Any) -> Any:
    # Missing-field errors report the whole request body as their input, so a
    # valid password can appear inside an error about a different field.
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _redact_error(error: dict[str, Any]) -> dict[str, Any]:
    if "input" not in error:
        return error
    if any(_is_sensitive(part) for part in error.get("loc", ())):
        return {**error, "input": REDACTED}
    return {**error, "input": _redact(error["input"])}


async def request_validation_error(
    _request: Request, exc: RequestValidationError
) -> Response:
    """Return validation details even when rejected input cannot be rendered as JSON."""
    # Rejected input may contain overflowing numbers, lone surrogates, or raw
    # non-UTF-8 bytes. Error rendering must not turn those failures into a 500.
    errors = jsonable_encoder(
        [_redact_error(error) for error in exc.errors()],
        custom_encoder={
            float: lambda value: value if math.isfinite(value) else str(value),
            bytes: lambda value: value.decode("utf-8", errors="backslashreplace"),
        },
    )
    return Response(
        content=json.dumps({"detail": errors}, ensure_ascii=True, allow_nan=False),
        status_code=422,
        media_type="application/json",
    )
