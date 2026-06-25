"""
RQ Worker 진입점.

API 서버와 별도의 터미널에서 실행한다.
  .venv/Scripts/Activate.ps1
  python worker.py

Worker가 시작되면 "agent" 큐에 등록된 작업을 가져와 처리한다.
작업 결과와 히스토리는 PostgreSQL에 저장된다.
"""
# load_dotenv()를 가장 먼저 호출해야 DATABASE_URL, REDIS_URL 등이 설정된 후
# 아래 모듈들이 import된다.
from dotenv import load_dotenv

load_dotenv()

from redis import Redis  # noqa: E402
#from rq import Worker, Queue  # noqa: E402
from rq import Queue, SimpleWorker

from app.core.config import settings  # noqa: E402

if __name__ == "__main__":
    redis_conn = Redis.from_url(settings.redis_url)

    # Worker가 처리할 큐 목록. API 서버의 task_queue와 이름이 일치해야 한다.
    queue = Queue(name="agent", connection=redis_conn)

    print(f"RQ Worker 시작 | Redis: {settings.redis_url} | Queue: agent")

    # worker.work(): Worker가 큐를 감시하며 작업이 들어오면 처리한다.
    # with_scheduler=True → 예약된 작업(scheduled jobs)도 처리 가능
    worker = SimpleWorker(queues=[queue], connection=redis_conn)
    worker.work(with_scheduler=True)
