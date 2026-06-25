# AI Agent Task Orchestrator API

FastAPI 기반의 **AI Agent 백엔드 포트폴리오 프로젝트**입니다.

사용자의 자연어 요청을 AI Agent가 이해하고, 실행 계획을 생성하며, 긴 작업은 비동기 Job으로 처리하고, 실행 히스토리를 관리하는 구조를 구현합니다. 이후 개인 컨텍스트 RAG, 메모리 큐, Tool Calling, Google Sheets 연동, 작업 승인 구조를 추가하여 실무형 AI Agent Orchestrator로 확장하는 것을 목표로 합니다.

---

## 1. 프로젝트 목적

이 프로젝트의 목적은 단순한 LLM API 호출을 넘어, 실제 AI Agent 서비스에 필요한 백엔드 구조를 직접 구현해보는 것입니다.

주요 목표는 다음과 같습니다.

* 자연어 요청을 구조화된 Agent 실행 계획으로 변환
* LLM 작업을 비동기 Job으로 관리
* 작업 상태와 결과를 재조회할 수 있는 구조 구현
* Agent 실행 히스토리 저장
* 개인 컨텍스트와 최근 작업 메모리를 활용하는 Agent 구조로 확장
* 외부 도구 실행 전 사용자 승인 구조 도입
* AI Agent Engineering 직무에 설명 가능한 포트폴리오 구축

---

## 2. 현재 구현 상태

현재 구현된 기능은 다음과 같습니다.

| 구분          | 구현 내용                                   |
| ----------- | --------------------------------------- |
| 기본 서버 구조    | FastAPI 앱 구조, 설정 계층, Health Check       |
| LLM 설정 계층   | OpenAI API Key, 모델명 환경변수 관리             |
| Agent 계획 생성 | 자연어 요청을 기반으로 구조화된 실행 계획 생성              |
| Job 관리      | 긴 작업을 Job으로 등록하고 상태 조회                  |
| 비동기 실행      | FastAPI BackgroundTasks 기반 Agent Job 실행 |
| 결과 조회       | Job ID 기반 실행 결과 조회                      |
| 히스토리 관리     | Agent 요청과 결과 요약 저장 및 조회                 |

---

## 3. 핵심 기능

### Agent 계획 생성

사용자의 자연어 요청을 분석하여 목표, 실행 단계, 리스크, 다음 액션을 포함한 구조화된 계획을 생성합니다.

### 비동기 Job 처리

LLM 작업은 시간이 오래 걸릴 수 있으므로 Job으로 등록하고 백그라운드에서 실행합니다. 사용자는 Job ID를 통해 상태와 결과를 조회할 수 있습니다.

### 실행 히스토리 관리

Agent가 처리한 요청과 결과 요약을 저장하여 과거 작업 흐름을 확인할 수 있습니다.

### 메모리 큐 확장 예정

최근 사용자 요청, Agent 응답, 도구 실행 결과, 실패 원인 등을 Redis 기반 메모리 큐로 관리하여 Agent가 최근 작업 흐름을 이어서 판단할 수 있도록 확장할 예정입니다.

### 개인 컨텍스트 RAG 확장 예정

사용자의 경력, 프로젝트 상태, 학습 목표, 과거 작업 기록을 검색 가능한 개인 컨텍스트로 관리하고, Agent 계획 생성에 반영할 예정입니다.

### Tool Calling 확장 예정

Agent가 필요한 도구를 선택하고 실행할 수 있도록 Tool Calling 구조를 추가할 예정입니다.

### 작업 승인 구조 확장 예정

Google Sheets 업데이트처럼 외부 시스템을 변경하는 작업은 즉시 실행하지 않고, 사용자 승인 후 실행하도록 설계할 예정입니다.

---

## 4. 기술스택

| 영역                     | 기술                  |
| ---------------------- | ------------------- |
| Backend Framework      | FastAPI             |
| Data Validation        | Pydantic            |
| Environment Management | pydantic-settings   |
| LLM Integration        | OpenAI API          |
| Tool Calling           | OpenAI Tool Calling |
| Vector Database        | Chroma              |
| Embedding              | OpenAI Embeddings   |
| Memory Queue           | Redis               |
| Async Job Queue        | RQ                  |
| Database               | PostgreSQL          |
| ORM                    | SQLAlchemy          |
| External Search        | Tavily Search API   |
| External Integration   | Google Sheets API   |
| Report Format          | Markdown            |

---

## 5. 프로젝트 구조

```text
agent-task-orchestrator-api/
├─ app/
│  ├─ main.py
│  ├─ core/
│  ├─ api/
│  ├─ schemas/
│  └─ services/
├─ docs/
│  ├─ project-definition.md
│  ├─ step-01-fastapi-project-structure.md
│  ├─ step-02-llm-settings-layer.md
│  ├─ step-03-agent-plan-api.md
│  ├─ step-04-job-management.md
│  ├─ step-05-background-tasks.md
│  └─ step-06-history.md
├─ .env.example
├─ requirements.txt
└─ README.md
```

---

## 6. 실행 방법

가상환경을 생성하고 패키지를 설치합니다.

```bash
python -m venv .venv
```

Windows PowerShell 기준:

```powershell
.venv\Scripts\Activate.ps1
```

패키지 설치:

```bash
pip install -r requirements.txt
```

환경변수 파일을 준비합니다.

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` 파일에 아래 항목을 입력합니다.

```env
DATABASE_URL=postgresql://postgres:비밀번호@localhost:5432/agent_db
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-your-key-here
```

**PostgreSQL 준비 (Step 07 이후 필수)**

```powershell
docker run -d --name agent-db -e POSTGRES_PASSWORD=password -e POSTGRES_DB=agent_db -p 5432:5432 postgres:16
```

**Redis 준비 (Step 08 이후 필수)**

```powershell
docker run -d --name agent-redis -p 6379:6379 redis:7
```

> PostgreSQL 또는 Redis가 이미 로컬에 설치되어 있다면 Docker 없이 사용해도 됩니다.

> 서버 최초 실행 시 `jobs`, `history` 테이블이 자동으로 생성됩니다.

**터미널 1 — API 서버 실행:**

```powershell
uvicorn app.main:app --reload
```

**터미널 2 — RQ Worker 실행 (Step 08 이후 필수):**

```powershell
python worker.py
```

Worker가 시작되면 아래와 같은 메시지가 출력됩니다.

```
RQ Worker 시작 | Redis: redis://localhost:6379/0 | Queue: agent
```

> API 서버와 Worker는 별도 터미널에서 동시에 실행되어야 합니다.
> Worker 없이 `POST /agent/jobs`를 호출하면 Job이 Redis 큐에 쌓이고, Worker가 시작될 때 처리됩니다.

Swagger UI 접속:

```text
http://127.0.0.1:8000/docs
```

---

## 7. 문서

프로젝트의 상세 정의는 아래 문서에서 확인할 수 있습니다.

```text
docs/project-definition.md
```

단계별 구현 기록은 `docs/step-xx` 문서에 정리합니다.

---

## 8. 포트폴리오 관점의 의미

이 프로젝트는 AI Agent Engineering 직무에서 중요한 다음 역량을 보여주는 것을 목표로 합니다.

* LLM API를 백엔드 서비스 기능으로 통합하는 역량
* Agent 실행 계획을 구조화하는 역량
* 비동기 작업과 상태를 관리하는 역량
* 실행 히스토리와 메모리를 다루는 역량
* RAG 기반 개인 컨텍스트 활용 역량
* Tool Calling 기반 외부 도구 실행 설계 역량
* Human-in-the-loop 기반 안전한 승인 구조 설계 역량
* FastAPI 기반 백엔드 아키텍처 설계 역량

---

## 9. 최종 목표

이 프로젝트의 최종 목표는 **사용자의 자연어 요청을 기반으로 개인 컨텍스트와 최근 작업 메모리를 참고하고, 필요한 도구를 활용하여 계획 수립부터 결과물 생성까지 수행하는 AI Agent 백엔드 시스템**을 구현하는 것입니다.