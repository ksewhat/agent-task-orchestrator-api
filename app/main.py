from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import health
from app.api.routes import agent
from app.api.routes import job
from app.api.routes import agent_job

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health.router, tags=["Health"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])
app.include_router(job.router, prefix="/jobs", tags=["Jobs"])
app.include_router(agent_job.router, prefix="/agent/jobs", tags=["Agent Jobs"])