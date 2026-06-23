# Agent Task Orchestrator API

FastAPI 기반 Agent Task Orchestrator 백엔드 서버입니다.

---

## 실행 환경

- Python 3.11 이상
- Windows PowerShell 기준

---

## 시작하기

### 1. 가상환경 생성

```powershell
python -m venv .venv
```

### 2. 가상환경 활성화

```powershell
.venv\Scripts\Activate.ps1
```

> PowerShell 실행 정책 오류가 발생하면 아래 명령어를 먼저 실행하세요.
>
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. 패키지 설치

```powershell
pip install -r requirements.txt
```

### 4. 환경변수 파일 생성

`.env.example`을 복사해 `.env` 파일을 만듭니다.

```powershell
Copy-Item .env.example .env
```

메모장으로 `.env` 파일을 열어 필요한 값을 입력합니다.

```powershell
notepad .env
```

`.env` 파일 예시:

```env
APP_NAME=Agent Task Orchestrator API
APP_ENV=local
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

> **주의:** `OPENAI_API_KEY`를 Git에 커밋하면 절대 안 됩니다.
> `.env` 파일은 `.gitignore`에 추가되어 있어야 합니다.
>
> `OPENAI_API_KEY`가 없어도 서버는 정상 시작됩니다.
> `/agent/plan` 호출 시에만 503 에러가 반환됩니다.

### 5. 서버 실행

```powershell
uvicorn app.main:app --reload
```

---

## API 확인

| 항목 | URL |
|------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |
| Agent Plan | POST http://localhost:8000/agent/plan |

### Health Check 테스트

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health -Method GET
```

응답 예시:

```json
{
  "status": "ok",
  "service": "Agent Task Orchestrator API"
}
```

### Agent Plan API 테스트

```powershell
$body = '{"user_request": "FastAPI 서버를 AWS EC2에 배포하는 계획을 세워줘"}'
Invoke-RestMethod -Uri http://localhost:8000/agent/plan -Method POST -Body $body -ContentType "application/json"
```

정상 응답 예시:

```json
{
  "goal": "FastAPI 서버를 AWS EC2에 성공적으로 배포",
  "summary": "로컬 개발 환경에서 검증된 FastAPI 서버를 AWS EC2 인스턴스에 배포한다.",
  "steps": [
    {
      "order": 1,
      "title": "EC2 인스턴스 생성",
      "description": "AWS 콘솔에서 적절한 인스턴스 타입을 선택하고 생성한다.",
      "expected_output": "실행 중인 EC2 인스턴스, Public IP"
    }
  ],
  "risks": ["보안 그룹 설정 누락", "환경변수 미설정"],
  "next_action": "AWS 콘솔에 로그인하여 EC2 인스턴스를 생성한다."
}
```

#### 에러 응답 예시

**OPENAI_API_KEY 없음 (503)**:

```json
{ "detail": "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 입력해주세요." }
```

**빈 요청 (400)**:

```json
{ "detail": "user_request는 비어 있을 수 없습니다." }
```

**OpenAI API 호출 실패 (502)**:

```json
{ "detail": "OpenAI API 호출에 실패했습니다: ..." }
```
