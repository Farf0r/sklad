# Образ приложения «Склад». Сборка и запуск — через Docker Compose (make up), см. docs/docker.md.

# Базовый образ закреплён точной версией и digest: сборка через месяц возьмёт тот же образ.
ARG PYTHON_IMAGE=python:3.13.18-slim-trixie@sha256:76baad6037690d6e8c4397fbcaef17bca6f19eecef822b708fe8fa3417d30bb5

# ---------- сборка зависимостей ----------
FROM ${PYTHON_IMAGE} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt requirements-lock.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt -c requirements-lock.txt

# ---------- образ для запуска ----------
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    APP_ENV=prod \
    BACKUP_DIR=/backups

# pg_dump и pg_restore для резервного копирования; версия 17, как у сервера БД
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client \
 && rm -rf /var/lib/apt/lists/*

# пользователь без пароля и оболочки: приложение не работает от root
RUN groupadd --system --gid 10001 sklad \
 && useradd --system --uid 10001 --gid sklad --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin sklad \
 && install -d -o sklad -g sklad -m 750 /backups

COPY --from=build /opt/venv /opt/venv
WORKDIR /app
# код принадлежит root, пользователь sklad может его только читать
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
RUN python -m compileall -q app migrations

USER sklad
EXPOSE 8000

# docker stop отправляет SIGTERM; uvicorn завершает текущие запросы и закрывает подключения к БД
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# exec-форма: uvicorn — процесс с PID 1 и сам получает сигнал остановки
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "10"]
