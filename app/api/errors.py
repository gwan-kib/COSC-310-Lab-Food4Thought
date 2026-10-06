import json
import math

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError


async def request_validation_error_response(
    request: Request, exc: RequestValidationError
) -> Response:
    """Return validation details even when rejected input cannot be rendered as JSON."""
    # Rejected input may contain overflowing numbers, lone surrogates, or raw
    # non-UTF-8 bytes. Error rendering must not turn those failures into a 500.
    errors = jsonable_encoder(
        exc.errors(),
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
