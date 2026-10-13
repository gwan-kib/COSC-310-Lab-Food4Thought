# Expose Food4Thought's health endpoint so contributors and tooling can check whether
# the API process responds.
# This liveness route does not depend on restaurant storage, allowing it to work even
# when the data file is unavailable.

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is up and able to answer requests.

    This is a liveness check only; it does not read restaurant data, so a
    missing or broken data file will not make it fail.
    """
    return {"status": "ok"}
