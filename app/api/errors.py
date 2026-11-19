# Serialize Food4Thought's request-validation failures as JSON while preserving
# useful field diagnostics. Safely encode rejected non-finite numbers, Unicode, and
# bytes, and redact submitted passwords from every part of a 422 response.

import json
import math
from typing import Any

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

# Compared case-insensitively against field names and error locations.
SENSITIVE_FIELDS = frozenset({"password"})
REDACTED = "[redacted]"
# Built-in Pydantic errors whose messages never contain the submitted value. Any
# other error on a password field, such as a custom validator, gets a generic message.
SAFE_SENSITIVE_ERROR_TYPES = frozenset(
    {"missing", "string_type", "string_too_short", "string_too_long", "extra_forbidden"}
)
SENSITIVE_ERROR_MESSAGE = "Invalid password"


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


def _submitted_secrets(value: Any) -> set[str]:
    if isinstance(value, dict):
        secrets = set()
        for key, item in value.items():
            if _is_sensitive(key) and isinstance(item, str) and item:
                secrets.add(item)
            else:
                secrets |= _submitted_secrets(item)
        return secrets
    if isinstance(value, list):
        return set().union(*(_submitted_secrets(item) for item in value))
    return set()


def _scrub(value: Any, secrets: set[str]) -> Any:
    # A model-level validator can quote a password in its message or context even
    # though its error is not located on the password field.
    if isinstance(value, dict):
        return {key: _scrub(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item, secrets) for item in value]
    if isinstance(value, (str, Exception)):
        text = str(value)
        for secret in sorted(secrets, key=len, reverse=True):
            text = text.replace(secret, REDACTED)
        return text
    return value


def _redact_error(error: dict[str, Any]) -> dict[str, Any]:
    error = dict(error)
    secrets = _submitted_secrets(error.get("input"))
    if any(_is_sensitive(part) for part in error.get("loc", ())):
        if isinstance(error.get("input"), str) and error["input"]:
            secrets.add(error["input"])
        if "input" in error:
            error["input"] = REDACTED
        if error.get("type") not in SAFE_SENSITIVE_ERROR_TYPES:
            error["msg"] = SENSITIVE_ERROR_MESSAGE
            error.pop("ctx", None)
    elif "input" in error:
        error["input"] = _redact(error["input"])
    if secrets:
        for field in ("msg", "ctx"):
            if field in error:
                error[field] = _scrub(error[field], secrets)
    return error


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
