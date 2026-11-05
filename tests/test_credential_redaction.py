"""Check that Food4Thought's shared 422 handler never echoes submitted passwords.
Registration and login (#79/#80) reuse this handler, so these checks use a
test-only route with a password field instead of an unimplemented endpoint.
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.api.errors import request_validation_error

REDACTED = "[redacted]"
PASSWORD = "correct-horse-battery-staple"


class CredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=12)


def _client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, request_validation_error)

    @app.post("/credentials")
    def accept_credentials(_body: CredentialRequest) -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_rejected_password_value_is_redacted():
    response = _client().post("/credentials", json={"email": "a@example.invalid", "password": "tiny-pw"})

    assert response.status_code == 422
    assert "tiny-pw" not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "password"]
    assert error["input"] == REDACTED
    assert error["ctx"] == {"min_length": 12}


def test_valid_password_in_a_rejected_body_is_redacted():
    # A missing field reports the whole body as input, including a valid password.
    response = _client().post("/credentials", json={"password": PASSWORD})

    assert response.status_code == 422
    assert PASSWORD not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "email"]
    assert error["input"] == {"password": REDACTED}


def test_wrongly_cased_and_nested_password_keys_are_redacted():
    response = _client().post(
        "/credentials",
        json={"email": "a@example.invalid", "password": PASSWORD, "Password": "other-secret",
              "profile": {"password": "nested-secret"}},
    )

    assert response.status_code == 422
    assert "other-secret" not in response.text
    assert "nested-secret" not in response.text
    inputs = {tuple(error["loc"]): error["input"] for error in response.json()["detail"]}
    assert inputs[("body", "Password")] == REDACTED
    assert inputs[("body", "profile")] == {"password": REDACTED}


def test_non_credential_input_is_still_reported():
    response = _client().post("/credentials", json={"email": 7, "password": PASSWORD})

    assert response.status_code == 422
    assert PASSWORD not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "email"]
    assert error["input"] == 7
