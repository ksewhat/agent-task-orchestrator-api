from sqlalchemy import JSON, Column, DateTime, Integer, String

from app.db.base import Base


class JobModel(Base):
    """jobs 테이블의 ORM 모델.

    Pydantic의 JobResponse와 역할이 다르다.
    - ORM 모델: DB 테이블 행(row)을 파이썬 객체로 표현
    - Pydantic 모델: HTTP 요청/응답 데이터 검증 및 직렬화
    실제 사용 시에는 ORM 모델을 읽어와 Pydantic 모델로 변환해서 반환한다.
    """

    __tablename__ = "jobs"

    # Column(타입, 옵션): 테이블 컬럼 정의
    job_id = Column(String, primary_key=True)
    status = Column(String(20), nullable=False)
    user_request = Column(String, nullable=False)
    context = Column(String, nullable=True)

    # DateTime(timezone=True) → TIMESTAMP WITH TIME ZONE 컬럼
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    # JSON 컬럼: AgentPlanResponse를 dict로 직렬화해서 저장
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True)


class HistoryModel(Base):
    """history 테이블의 ORM 모델."""

    __tablename__ = "history"

    entry_id = Column(String, primary_key=True)
    job_id = Column(String, nullable=True)
    user_request = Column(String, nullable=False)
    status = Column(String(20), nullable=False)
    goal = Column(String, nullable=True)
    step_count = Column(Integer, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
