# Контейнерное окружение

Образ приложения описан в `Dockerfile`. Что попадает в контекст сборки — `.dockerignore`, точные версии пакетов — `requirements-lock.txt`.

## 1. Образ приложения

- **Двухэтапная сборка.** На первом этапе в виртуальное окружение `/opt/venv` ставятся зависимости, во второй образ копируется только оно — без кеша pip и временных файлов сборки.
- **Воспроизводимость.** Базовый образ задан точной версией и digest (`python:3.13.X-slim-trixie@sha256:…`): тег могут перевыпустить, digest — нет. Версии всех пакетов, включая зависимости зависимостей, закреплены в `requirements-lock.txt` (он передаётся pip как ограничения `-c`).
- **Непривилегированный пользователь.** Приложение работает от пользователя `sklad` (uid 10001) без пароля и оболочки. Код в `/app` принадлежит root, `sklad` может его только читать. Писать можно только в `/backups`.
- **Ничего лишнего.** `.dockerignore` устроен как «белый список»: в контекст сборки попадают только `app/`, `migrations/`, `alembic.ini` и файлы зависимостей. `.env`, `.git`, тесты, резервные копии и журналы в образ попасть не могут.
- **Настройки — только переменными окружения.** В образе нет паролей и строки подключения: `DATABASE_URL` и `SECRET_KEY` передаются при запуске контейнера. Внутри образа заданы только `APP_ENV=prod` и `BACKUP_DIR=/backups`.
- **Корректное завершение.** `CMD` записан в exec-форме, поэтому uvicorn — процесс с PID 1 и сам получает `SIGTERM` от `docker stop`. Он перестаёт принимать запросы, дожидается текущих (не дольше 10 с, `--timeout-graceful-shutdown`), закрывает подключения к БД и пишет в журнал «Склад остановлен». Если бы `CMD` был строкой, PID 1 был бы `/bin/sh`, сигнал не дошёл бы до приложения и через 10 секунд Docker убил бы его (`SIGKILL`, код 137).
- **Healthcheck.** Docker раз в 10 секунд запрашивает `/health` изнутри контейнера; если база недоступна, `/health` отвечает 503 и контейнер становится `unhealthy`.
- `pg_dump` и `pg_restore` (пакет `postgresql-client` 17) — для резервного копирования из контейнера.

## 2. Сборка и проверка образа

```bash
docker build -t sklad:0.3.0 .
docker run --rm sklad:0.3.0 id                     # uid=10001(sklad) gid=10001(sklad)
docker run --rm sklad:0.3.0 ls -la /app            # только alembic.ini, app, migrations; владелец root
```

Запуск без базы данных — проверить настройки через переменные окружения, healthcheck и остановку:

```bash
docker run -d --name sklad-try -p 127.0.0.1:8080:8000 -e DATABASE_URL="postgresql+psycopg://sklad:x@127.0.0.1:5432/sklad" -e SECRET_KEY="test-key-0123456789abcdef" sklad:0.3.0
docker logs sklad-try                              # «Склад 0.3.0 запущен, окружение: prod»
curl http://127.0.0.1:8080/health                  # 503: {"status":"error","db":"unavailable",...}; в PowerShell — curl.exe
docker ps                                          # через ~45 с: (unhealthy)
docker stop sklad-try                              # меньше секунды
docker inspect --format "{{.State.ExitCode}}" sklad-try   # 0 — приложение завершилось само
docker logs sklad-try                              # в конце «Склад остановлен»
docker rm sklad-try
```

Запуск вместе с базой данных — через Docker Compose.

## 3. Обновление базового образа и зависимостей

```bash
docker pull python:3.13-slim-trixie
docker run --rm python:3.13-slim-trixie python --version          # например, 3.13.9
docker pull python:3.13.9-slim-trixie
docker image inspect --format "{{index .RepoDigests 0}}" python:3.13.9-slim-trixie
```

Полученный digest подставить в `ARG PYTHON_IMAGE` в `Dockerfile`. После изменения `requirements.txt` нужно обновить `requirements-lock.txt` — порядок описан в комментарии в начале файла.
