from fastapi import FastAPI

from app.api.routes import health

app = FastAPI(
    title="Food4Thought API",
    description="COSC 310 food-delivery application backend.",
)

app.include_router(health.router)
