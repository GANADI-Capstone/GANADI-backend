# ── 1단계: 의존성 설치 ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /app

# venv 생성 후 설치 → 2단계에서 통째로 복사 (경로 꼬임 없음)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 2단계: 런타임 ─────────────────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

RUN mkdir -p uploads

EXPOSE 8002
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8002"]
