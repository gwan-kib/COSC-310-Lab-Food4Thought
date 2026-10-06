from fastapi import FastAPI

from app.api.openapi import install_openapi
from app.api.routes import health, restaurants

app = FastAPI(
    title="Food4Thought API",
    description="COSC 310 food-delivery application backend.",
)

app.include_router(health.router)
app.include_router(restaurants.router)

install_openapi(app)
