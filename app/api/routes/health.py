# Expose Food4Thought's liveness check for local setup and automated checks. This
# route tests whether the API responds independently of restaurant storage, so
# success does not prove the data file is usable.

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is up and able to answer requests.

    This is a liveness check only; it does not read restaurant data, so a
    missing or broken data file will not make it fail.
    """
    return {"status": "ok"}
