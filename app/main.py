from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import health, agent, job, agent_job, history, memory


# asynccontextmanager: async def 함수를 yield 기준으로 시작/종료 로직으로 분리
# lifespan은 FastAPI 앱의 시작(startup)과 종료(shutdown) 시 실행할 코드를 정의함
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 서버 시작 시 실행 ---
    # 이 시점에 import해야 모든 ORM 모델이 Base.metadata에 등록된 상태가 됨
    from app.db.base import Base, engine
    import app.db.models  # noqa: F401 — 모델 파일을 import해야 테이블 정보가 Base에 등록됨

    # 테이블이 없으면 생성, 이미 있으면 그대로 유지 (데이터 보존)
    Base.metadata.create_all(bind=engine)
    yield
    # --- 서버 종료 시 실행 (현재는 별도 처리 없음) ---


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health.router, tags=["Health"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])
app.include_router(job.router, prefix="/jobs", tags=["Jobs"])
app.include_router(agent_job.router, prefix="/agent/jobs", tags=["Agent Jobs"])
app.include_router(history.router, prefix="/history", tags=["History"])
app.include_router(memory.router, prefix="/agent/memory", tags=["Memory"])
