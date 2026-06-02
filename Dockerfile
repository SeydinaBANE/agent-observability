FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .[workers,dashboard]

COPY core/ core/
COPY sdk/ sdk/
RUN pip install --no-cache-dir -e sdk/

COPY . .

FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

FROM base AS dashboard
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

FROM base AS worker
CMD ["celery", "-A", "workers.tasks", "worker", "--loglevel=info", "--concurrency=4"]

FROM base AS beat
CMD ["celery", "-A", "workers.tasks", "beat", "--loglevel=info"]
