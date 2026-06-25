from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# create_engine: DB 연결을 관리하는 엔진 객체 생성
# pool_pre_ping=True → 유휴 커넥션이 끊겼을 때 자동으로 재연결 시도
engine = create_engine(settings.database_url, pool_pre_ping=True)

# sessionmaker: Session을 찍어내는 공장(factory)
# autocommit=False → 명시적으로 commit() 해야 DB에 반영됨
# autoflush=False  → session.flush()를 자동으로 호출하지 않음
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# DeclarativeBase: 모든 ORM 모델 클래스가 상속할 공통 Base
# Base.metadata.create_all(engine) 호출 시 연결된 모든 테이블을 생성함
class Base(DeclarativeBase):
    pass
