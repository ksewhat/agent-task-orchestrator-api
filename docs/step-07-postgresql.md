# Step 07. PostgreSQL 기반 영구 저장소로 전환

> 학습 일자: 2026-06-25
> 목표: 인메모리 저장소를 PostgreSQL + SQLAlchemy로 교체해 서버 재시작 후에도 Job과 History를 유지한다.

---

## 1. 이번 단계에서 추가/수정한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/db/__init__.py` | 신규 | DB 패키지 선언 |
| `app/db/base.py` | 신규 | engine, SessionLocal, Base 정의 |
| `app/db/models.py` | 신규 | JobModel, HistoryModel ORM 클래스 |
| `app/core/config.py` | 수정 | `database_url` 설정 추가 |
| `app/services/job_store.py` | 수정 | 인메모리 → DB CRUD로 교체 |
| `app/services/history_store.py` | 수정 | 인메모리 → DB CRUD로 교체 |
| `app/main.py` | 수정 | lifespan으로 서버 시작 시 테이블 자동 생성 |
| `requirements.txt` | 수정 | `sqlalchemy`, `psycopg2-binary` 추가 |
| `.env.example` | 수정 | `DATABASE_URL` 항목 추가 |
| `README.md` | 수정 | PostgreSQL 설정 방법 추가 |

기존 라우터, 스키마, agent_runner는 변경 없다. 내부 저장 방식만 교체됐다.

---

## 2. ORM vs Pydantic — 두 가지 모델을 쓰는 이유

이번 단계에서 처음으로 SQLAlchemy ORM 모델과 Pydantic 모델이 같은 프로젝트에 공존한다.

| 구분 | 위치 | 역할 |
|------|------|------|
| ORM 모델 (`JobModel`) | `app/db/models.py` | DB 테이블 행(row)을 Python 객체로 표현 |
| Pydantic 모델 (`JobResponse`) | `app/schemas/job.py` | HTTP 응답 데이터 검증 및 JSON 직렬화 |

이 둘을 분리하는 이유는 역할이 다르기 때문이다.

ORM 모델은 "DB와 대화하는 언어"다. SQLAlchemy가 이 모델을 보고 SQL을 생성하고, DB에서 읽어온 값을 이 클래스의 인스턴스로 만들어준다. 반면 Pydantic 모델은 "HTTP와 대화하는 언어"다. 클라이언트에게 어떤 JSON 구조를 반환할지 정의한다.

실제 데이터 흐름:

```
DB에서 읽음 → ORM 객체 (JobModel) → _to_response() → Pydantic 객체 (JobResponse) → JSON 응답
```

---

## 3. `app/db/base.py` — engine, SessionLocal, Base 역할

```python
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass
```

**engine**: DB 서버와의 연결을 관리하는 객체. 직접 SQL을 실행하지 않고 Session을 통해 작업한다. `pool_pre_ping=True`는 오래된 연결이 끊겼을 때 자동으로 재연결을 시도하게 한다.

**SessionLocal**: Session 인스턴스를 만드는 공장(factory). `autocommit=False`는 "내가 직접 commit()을 호출해야 DB에 반영된다"는 설정이다. 실수로 중간에 데이터가 반영되는 것을 방지한다.

**Base**: 모든 ORM 모델 클래스가 상속하는 공통 부모. `Base.metadata.create_all(engine)`을 호출하면 Base를 상속한 모든 클래스의 테이블이 한 번에 생성된다.

---

## 4. `with SessionLocal() as session:` — context manager로 세션 관리

```python
with SessionLocal() as session:
    row = session.get(JobModel, job_id)
    session.commit()
```

`with` 블록을 벗어나면 `session.close()`가 자동으로 호출된다. 이렇게 하면 명시적으로 `session.close()`를 호출하는 것을 잊어도 연결 자원이 자동으로 반환된다.

`commit()`은 자동으로 호출되지 않는다. 쓰기 작업 후에는 반드시 `session.commit()`을 호출해야 DB에 반영된다. `commit()` 없이 블록을 벗어나면 변경 사항이 롤백된다.

---

## 5. `session.get(Model, pk)` — 기본키로 단건 조회

```python
row = session.get(JobModel, job_id)  # SELECT * FROM jobs WHERE job_id = ?
```

`session.get()`은 SQLAlchemy 2.0의 단건 조회 방식이다. 1.x의 `session.query(Model).filter_by(pk=value).first()`보다 간결하다. 결과가 없으면 `None`을 반환한다.

---

## 6. JSON 컬럼 — 복잡한 데이터 저장 방법

`result` 필드는 `AgentPlanResponse`라는 복잡한 중첩 구조다. 이것을 관계형 DB에 저장하는 방법은 여러 가지다.

**별도 테이블로 분리**: `steps` 테이블을 만들어 각 단계를 행으로 저장한다. 구조가 복잡해지고 JOIN이 필요해진다.

**JSON 컬럼 사용 (이번 방식)**: PostgreSQL의 JSON 컬럼에 dict로 직렬화해서 통째로 저장한다.

```python
# 저장: Pydantic 모델 → dict
row.result = result.model_dump() if result is not None else None

# 읽기: dict → Pydantic 모델
result = AgentPlanResponse(**row.result) if row.result else None
```

JSON 컬럼은 쿼리로 결과 내부 필드를 검색하기 어렵지만, 지금처럼 job_id로 job을 조회한 후 result 전체를 반환하는 용도라면 충분하다.

---

## 7. lifespan — 서버 시작 시 테이블 자동 생성

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.base import Base, engine
    import app.db.models  # 이 import가 있어야 Base에 모델이 등록됨
    Base.metadata.create_all(bind=engine)
    yield
```

`create_all(bind=engine)`: DB에 테이블이 없으면 생성하고, 이미 있으면 건드리지 않는다. 서버를 재시작해도 기존 데이터가 사라지지 않는 이유다.

`import app.db.models`가 반드시 필요한 이유: SQLAlchemy는 ORM 모델 클래스를 import했을 때 `Base.metadata`에 테이블 정보를 등록한다. import하지 않으면 `create_all()`이 어떤 테이블을 만들어야 하는지 알지 못한다.

---

## 8. status를 String 컬럼으로 저장하는 이유

```python
status = Column(String(20), nullable=False)
```

SQLAlchemy는 PostgreSQL 네이티브 ENUM 타입도 지원한다. 하지만 PostgreSQL 네이티브 ENUM은 새로운 값을 추가하려면 `ALTER TYPE` 명령이 필요하다. String 컬럼으로 저장하면 이 제약이 없다.

읽어올 때는 `JobStatus(row.status)`로 간단히 Enum으로 변환한다.

---

## 9. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| ORM 모델 | DB 테이블과 Python 클래스를 연결. Pydantic 모델과 역할이 다름 |
| `DeclarativeBase` | 모든 ORM 모델의 공통 부모, 테이블 메타데이터를 수집 |
| `SessionLocal` | Session을 찍어내는 factory. `with` 블록으로 자동 close |
| `create_all` | lifespan에서 서버 시작 시 테이블 생성 (이미 있으면 스킵) |
| JSON 컬럼 | 복잡한 중첩 데이터를 dict로 직렬화해 단일 컬럼에 저장 |
| 함수 시그니처 유지 | `job_store`, `history_store` 함수 인터페이스 변경 없이 내부만 교체 |

---

## 10. 다음 단계에서 할 것

- 실제 서버 재시작 후 데이터 유지 확인
- Alembic으로 DB 마이그레이션 관리 (스키마 변경 추적)
- 인증 미들웨어 추가 (히스토리 API 보호)
- Redis 기반 메모리 큐 추가
