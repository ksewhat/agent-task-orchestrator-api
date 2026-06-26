from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()
#같은 폴더에 있는 .env 파일의 데이터들을 컴퓨터 메모리에 임시로 올림

class Settings(BaseSettings):
    app_name: str = "Agent Task Orchestrator API"
    app_env: str = "local"

    # Optional: 없어도 서버가 시작됨. LLM 기능 사용 시점에 검증함.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # PostgreSQL 접속 URL. .env에 반드시 설정해야 서버가 정상 기동된다.
    database_url: str = "postgresql://postgres:password@localhost:5432/agent_db"

    # Redis 접속 URL. Agent Job 큐와 메모리 큐에 사용된다.
    redis_url: str = "redis://localhost:6379/0"

    # Redis 메모리 큐에 보관할 최대 이벤트 수 (MEMORY_MAX_SIZE 환경변수로 덮어쓸 수 있음)
    memory_max_size: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
#클래스 인스턴스 생성
