# Create Food4Thought's FastAPI application and connect the backend routes to the
# frontend pages.
# It registers request-error handling and OpenAPI customization, serves both pages, and
# redirects the root URL to restaurant discovery.

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import request_validation_error
from app.api.openapi import install_openapi
from app.api.routes import health, restaurants

# Resolved from this file, not the working directory, so uvicorn can start anywhere.
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"

app = FastAPI(
    title="Food4Thought API",
    description="COSC 310 food-delivery application backend.",
)

app.add_exception_handler(RequestValidationError, request_validation_error)

app.include_router(health.router)
app.include_router(restaurants.router)

install_openapi(app)

# The static customer page calls the same REST API as any other client.
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/", include_in_schema=False)
def open_frontend() -> RedirectResponse:
    return RedirectResponse("/app/")
