"""Check that Food4Thought's shared 422 handler never echoes submitted passwords.
Registration and login (#79/#80) reuse this handler, so these checks use test-only
routes, including validators that put passwords in field and model diagnostics.
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.api.errors import request_validation_error

REDACTED = "[redacted]"
PASSWORD = "correct-horse-battery-staple"


class CredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=12)


class LeakyValidatorRequest(BaseModel):
    """Custom validators that wrongly put submitted values in their error messages."""

    password: str
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str, info: ValidationInfo) -> str:
        if "@" not in value:
            raise ValueError(f"email {value!r} needs an @")
        password = info.data.get("password")
        if password and password.endswith(value):
            raise PydanticCustomError(
                "email_matches_password_suffix",
                "Email {email} matches the end of password {submitted}",
                {"email": value, "submitted": password},
            )
        return value

    @field_validator("password")
    @classmethod
    def password_not_common(cls, value: str) -> str:
        if value.startswith("common"):
            raise ValueError(f"password {value!r} is too common")
        return value

    @model_validator(mode="after")
    def password_differs_from_email(self):
        if self.password.startswith(self.email):
            raise ValueError(f"password {self.password!r} must not start with the email")
        return self


def _client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, request_validation_error)

    @app.post("/credentials")
    def accept_credentials(_body: CredentialRequest) -> dict[str, bool]:
        return {"ok": True}

    @app.post("/leaky")
    def accept_leaky(_body: LeakyValidatorRequest) -> dict[str, bool]:
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
    assert error["msg"] == "String should have at least 12 characters"


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


def test_password_in_a_custom_field_validator_message_is_redacted():
    secret = "common-password-123"
    response = _client().post("/leaky", json={"email": "a@example.invalid", "password": secret})

    assert response.status_code == 422
    assert secret not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "password"]
    assert error["input"] == REDACTED
    assert error["msg"] == "Invalid password"
    assert "ctx" not in error


def test_password_in_a_whole_model_validator_message_is_redacted():
    secret = "a@example.invalid-and-more"
    response = _client().post("/leaky", json={"email": "a@example.invalid", "password": secret})

    assert response.status_code == 422
    assert secret not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body"]
    assert error["input"] == {"email": "a@example.invalid", "password": REDACTED}
    assert error["msg"] == f"Value error, password '{REDACTED}' must not start with the email"


def test_custom_messages_for_other_fields_are_kept():
    response = _client().post("/leaky", json={"email": "no-at-sign", "password": PASSWORD})

    assert response.status_code == 422
    assert PASSWORD not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "email"]
    assert error["msg"] == "Value error, email 'no-at-sign' needs an @"
    assert error["input"] == "no-at-sign"


def test_password_in_another_fields_message_and_context_is_redacted():
    email = "a@example.invalid"
    password = f"unique-password-ending-in-{email}"

    response = _client().post("/leaky", json={"email": email, "password": password})

    assert response.status_code == 422
    assert password not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "email"]
    assert error["input"] == email
    assert error["msg"] == f"Email {email} matches the end of password {REDACTED}"
    assert error["ctx"] == {"email": email, "submitted": REDACTED}
