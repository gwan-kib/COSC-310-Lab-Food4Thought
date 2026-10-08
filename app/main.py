from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.errors import request_validation_error
from app.api.openapi import install_openapi
from app.api.routes import health, restaurants

app = FastAPI(
    title="Food4Thought API",
    description="COSC 310 food-delivery application backend.",
)

app.add_exception_handler(RequestValidationError, request_validation_error)

app.include_router(health.router)
app.include_router(restaurants.router)

install_openapi(app)
