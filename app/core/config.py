from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    app_name: str = "Agent Task Orchestrator API"
    app_env: str = "local"

    class Config:
        env_file = ".env"


settings = Settings()
