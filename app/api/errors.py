# Serialize Food4Thought's request-validation failures as JSON while preserving
# useful field diagnostics. Safely encode rejected non-finite numbers, Unicode, and
# bytes, and redact submitted passwords from every part of a 422 response.

import json
import math
from typing import Any

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic_core import PydanticKnownError

# Compared case-insensitively against field names and error locations.
SENSITIVE_FIELDS = frozenset({"password"})
REDACTED = "[redacted]"
# Built-in Pydantic errors whose messages never contain the submitted value. Any
# other error on a password field, such as a custom validator, gets a generic message.
SAFE_SENSITIVE_ERROR_TYPES = frozenset(
    {"missing", "string_type", "string_too_short", "string_too_long", "extra_forbidden"}
)
SENSITIVE_ERROR_MESSAGE = "Invalid password"
# Endpoints whose bodies carry credentials. A body sent with the wrong content type
# reaches the handler as raw text, which field-based redaction cannot see inside.
CREDENTIAL_PATHS = frozenset({"/customers", "/auth/login"})
STRING_LENGTH_ERROR_TYPES = frozenset({"string_too_short", "string_too_long"})


def _is_sensitive(name: object) -> bool:
    return isinstance(name, str) and name.casefold() in SENSITIVE_FIELDS


def _redact(value: Any, secrets: set[str]) -> Any:
    # Missing-field errors report the whole request body as their input, so a
    # valid password can appear inside an error about a different field.
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive(key) else _redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str) and any(secret in value for secret in secrets):
        return REDACTED
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


def _scrub(value: Any, forms: list[str]) -> Any:
    # Cross-field and model validators can quote passwords in their diagnostics.
    if isinstance(value, dict):
        return {key: _scrub(item, forms) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item, forms) for item in value]
    if isinstance(value, (str, Exception)):
        # Insert the marker after matching so it cannot be matched as a password.
        parts = [str(value)]
        for form in forms:
            parts = [piece for part in parts for piece in part.split(form)]
        return REDACTED.join(parts)
    return value


def _uses_fixed_message(error: dict[str, Any]) -> bool:
    # Match the canonical text because custom validators can reuse a built-in code.
    # String length messages may use schema bounds. Other formatted errors may
    # include submitted values, so require a context-free message for those.
    kind = error.get("type")
    context = error.get("ctx") if kind in STRING_LENGTH_ERROR_TYPES else None
    try:
        return error.get("msg") == PydanticKnownError(kind, context).message()
    except (KeyError, TypeError, OverflowError):
        return False


def _redact_error(error: dict[str, Any], body_secrets: set[str]) -> dict[str, Any]:
    error = dict(error)
    secrets = body_secrets | _submitted_secrets(error.get("input"))
    if any(_is_sensitive(part) for part in error.get("loc", ())):
        if isinstance(error.get("input"), str) and error["input"]:
            secrets.add(error["input"])
        if "input" in error:
            error["input"] = REDACTED
        if error.get("type") not in SAFE_SENSITIVE_ERROR_TYPES:
            error["msg"] = SENSITIVE_ERROR_MESSAGE
            error.pop("ctx", None)
            return error
    elif "input" in error:
        error["input"] = _redact(error["input"], secrets)
    if secrets:
        # Include !r output without its surrounding quotes.
        forms = secrets | {repr(secret)[1:-1] for secret in secrets}
        longest_first = sorted(forms, key=len, reverse=True)
        if "msg" in error and not _uses_fixed_message(error):
            error["msg"] = _scrub(error["msg"], longest_first)
        if "ctx" in error:
            error["ctx"] = _scrub(error["ctx"], longest_first)
    return error


async def request_validation_error(
    request: Request, exc: RequestValidationError
) -> Response:
    """Return validation details even when rejected input cannot be rendered as JSON."""
    # An individual error's input may contain only the field being validated.
    body_secrets = _submitted_secrets(exc.body)
    # Rejected input may contain overflowing numbers, lone surrogates, or raw
    # non-UTF-8 bytes. Error rendering must not turn those failures into a 500.
    redacted = [_redact_error(error, body_secrets) for error in exc.errors()]
    if request.url.path in CREDENTIAL_PATHS and not isinstance(exc.body, dict):
        redacted = [{key: value for key, value in error.items() if key != "input"}
                    for error in redacted]
    errors = jsonable_encoder(
        redacted,
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
