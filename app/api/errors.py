import json
from math import isfinite

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError


async def request_validation_error(
    _request: Request, exc: RequestValidationError
) -> Response:
    """Return 422 even when rejected input cannot be encoded by JSONResponse."""
    errors = jsonable_encoder(
        exc.errors(),
        custom_encoder={float: lambda value: value if isfinite(value) else str(value)},
    )
    # Invalid inputs can contain non-finite numbers or unpaired surrogates.
    # Keep diagnostics, but stringify non-finite numbers and escape Unicode.
    return Response(
        content=json.dumps({"detail": errors}, ensure_ascii=True, allow_nan=False),
        status_code=422,
        media_type="application/json",
    )
