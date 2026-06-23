from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
    }
#Decorator, 함수 위에 씌우는 '기능 모자' 같은 거
#"바로 밑에 있는 health_check 함수를 인터넷 주소창 /health랑 연결해 줄게!"라는 FastAPI의 특수 모자
#딕셔너리(Dictionary) 반환, 
#FastAPI가 이걸 알아서 웹 브라우저가 이해하는 JSON 형식({"status": "ok"})으로 변환해 줌
