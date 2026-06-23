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
```

> **주의:** `OPENAI_API_KEY`를 Git에 커밋하면 절대 안 됩니다.
> `.env` 파일은 `.gitignore`에 추가되어 있어야 합니다.
>
> `OPENAI_API_KEY`는 현재 단계에서 선택 사항입니다.
> 값이 없어도 서버는 정상 시작되며, LLM 기능을 사용하는 시점에 오류가 발생합니다.

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

### Health Check 테스트

PowerShell에서 직접 호출:

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
