from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import health

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health.router, tags=["health"])
