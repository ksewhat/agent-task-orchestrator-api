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

    class Config:
        env_file = ".env"


settings = Settings()
#클래스 인스턴스 생성
