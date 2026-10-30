# Контейнерное окружение

Приложение и PostgreSQL запускаются в контейнерах Docker одной командой `make up`. Описание окружения — `Dockerfile` (образ приложения) и `compose.yaml` (сервисы, сеть, тома).

## 1. Состав

| Сервис | Образ | Что делает | Порты наружу |
|---|---|---|---|
| `db` | `postgres:17.X-trixie@sha256:…` (официальный) | база данных | нет |
| `migrate` | `sklad:<версия>` | применяет миграции и завершается | нет |
| `app` | `sklad:<версия>` (собирается из `Dockerfile`) | приложение (uvicorn) | `127.0.0.1:8080` |

```
 браузер ── 127.0.0.1:8080 ──► app:8000 ─┐
                       сеть frontend      │ сеть backend (internal)
                                          ├──► db:5432 ◄── migrate
                                          │
 том backups ◄── /backups (app)      том db-data ◄── /var/lib/postgresql/data (db)
```

Порядок запуска задан в `depends_on`: `db` становится `healthy` → `migrate` применяет миграции и завершается с кодом 0 → запускается `app`. Если миграции не прошли, приложение не запускается.

## 2. Запуск

Нужны Docker (на Windows — Docker Desktop с WSL 2) и выполненный `make setup`: он создаёт `.env` и дописывает в него пароли для контейнеров.

```bash
make up                     # сборка образа и запуск
make container-createadmin  # администратор (пароль спросит в консоли)
```

Приложение: http://127.0.0.1:8080, проверка работоспособности: http://127.0.0.1:8080/health.

| Команда | Что делает |
|---|---|
| `make up` | сборка образа и запуск; ждёт, пока все сервисы станут `healthy` |
| `make down` | останавливает и удаляет контейнеры; **тома с данными остаются** |
| `make container-migrate` | применить миграции |
| `make container-backup` | резервная копия базы в том `backups` |
| `make container-restore` | восстановление из последней копии (`FILE=/backups/имя.dump` — из указанной) |
| `make container-createadmin` | создать администратора |
| `docker compose ps` | состояние сервисов и healthcheck |
| `docker compose logs -f app` | журнал приложения |

Запуск в контейнерах не мешает локальной разработке: `make run` работает на порту 8000 с локальным PostgreSQL, контейнерное приложение — на 8080 со своей базой.

## 3. Образ приложения

- **Двухэтапная сборка.** На первом этапе в виртуальное окружение `/opt/venv` ставятся зависимости, во второй образ копируется только оно — без кеша pip и временных файлов сборки.
- **Воспроизводимость.** Базовый образ задан точной версией и digest (`python:3.13.X-slim-trixie@sha256:…`): тег могут перевыпустить, digest — нет. Версии всех пакетов, включая зависимости зависимостей, закреплены в `requirements-lock.txt` (он передаётся pip как ограничения `-c`).
- **Непривилегированный пользователь.** Приложение работает от пользователя `sklad` (uid 10001) без пароля и оболочки. Код в `/app` принадлежит root, `sklad` может его только читать. В Compose файловая система контейнера вообще только для чтения (`read_only`), писать можно только в `/backups` (том) и `/tmp` (tmpfs); все capabilities Linux отключены (`cap_drop: ALL`), повышение привилегий запрещено (`no-new-privileges`).
- **Ничего лишнего.** `.dockerignore` устроен как «белый список»: в контекст сборки попадают только `app/`, `migrations/`, `alembic.ini` и файлы зависимостей. `.env`, `.git`, тесты, резервные копии и журналы в образ попасть не могут.
- **Настройки — только переменными окружения.** В образе нет паролей и строки подключения: `DATABASE_URL` и `SECRET_KEY` передаются при запуске контейнера (раздел 4). Внутри образа заданы только `APP_ENV=prod` и `BACKUP_DIR=/backups`.
- **Корректное завершение.** `CMD` записан в exec-форме, поэтому uvicorn — процесс с PID 1 и сам получает `SIGTERM` от `docker stop`. Он перестаёт принимать запросы, дожидается текущих (не дольше 10 с, `--timeout-graceful-shutdown`), закрывает подключения к БД и пишет в журнал «Склад остановлен». Docker ждёт `stop_grace_period` (20 с) и только потом посылает `SIGKILL`. Если бы `CMD` был строкой, PID 1 был бы `/bin/sh`, сигнал не дошёл бы до приложения и его убили бы (код 137).
- **Healthcheck.** Docker раз в 10 секунд запрашивает `/health` изнутри контейнера; если база недоступна, `/health` отвечает 503 и контейнер становится `unhealthy`.
- `pg_dump` и `pg_restore` (пакет `postgresql-client` 17, как сервер) — для резервного копирования из контейнера.

Собрать и посмотреть образ без Compose:

```bash
docker build -t sklad:dev .
docker run --rm sklad:dev id                 # uid=10001(sklad) gid=10001(sklad)
docker run --rm sklad:dev ls -la /app        # только alembic.ini, app, migrations; владелец root
```

## 4. Настройки и пароли

Все настройки передаются переменными окружения (раздел `x-app-env` в `compose.yaml`). Значения паролей Docker Compose берёт из файла `.env` в папке проекта — он не попадает ни в Git, ни в образ.

| Переменная в `.env` | Для чего |
|---|---|
| `SECRET_KEY` | ключ подписи cookie (общий с локальным запуском) |
| `POSTGRES_PASSWORD` | пароль суперпользователя `postgres` в контейнере `db` |
| `SKLAD_DB_PASSWORD` | пароль пользователя `sklad`, от которого работает приложение |
| `SKLAD_PORT` | необязательно: порт приложения на компьютере (по умолчанию 8080) |
| `LOG_LEVEL` | необязательно: уровень журнала |

`make setup` генерирует `POSTGRES_PASSWORD` и `SKLAD_DB_PASSWORD` случайными (32 символа). Если пароля нет, `docker compose` не запустится и подскажет, что выполнить.

При первом запуске (пустой том) контейнер `db` выполняет `docker/initdb/10-app-user.sql`: создаёт пользователя `sklad` без прав суперпользователя (не больше 20 подключений) и базу `sklad`, владельцем которой он является. Приложение не знает пароль `postgres`.

Пароли из `.env` используются только при **создании** тома: если поменять их в `.env` позже, в базе останутся старые. Смена пароля — `ALTER ROLE` в базе и затем изменение `.env`.

## 5. Сети и порты

- `backend` — внутренняя сеть (`internal: true`): у контейнеров в ней нет выхода в интернет, к базе подключаются только `app` и `migrate` по имени `db`.
- `frontend` — через неё публикуется порт приложения.
- Порт базы `5432` **не публикуется**: с компьютера и из локальной сети к базе в контейнере не подключиться.
- Порт приложения опубликован только на `127.0.0.1`: с других компьютеров сети он недоступен.

## 6. Данные

| Том | Где в контейнере | Что хранит |
|---|---|---|
| `sklad_db-data` | `db:/var/lib/postgresql/data` | файлы базы данных |
| `sklad_backups` | `app:/backups` | резервные копии |

Данные хранятся в томах, а не в контейнерах, поэтому переживают:

- пересоздание контейнеров: `docker compose up -d --force-recreate`, `make down` + `make up`;
- обновление образа приложения: новая версия в `app/__init__.py` и `compose.yaml` → `make up` собирает `sklad:<новая версия>` и пересоздаёт `app`, а `migrate` применяет новые миграции к той же базе.

Данные удаляют только команды с томами: `docker compose down -v` или `docker volume rm sklad_db-data`. Перед ними нужна резервная копия.

## 7. Миграции, резервные копии и восстановление

Миграции применяются автоматически при каждом `make up` (сервис `migrate`), вручную — `make container-migrate`.

```bash
make container-backup                         # → /backups/sklad_<дата>_<время>.dump
docker compose exec app ls -l /backups        # список копий
make container-restore                        # из последней копии (спросит yes)
make container-restore FILE=/backups/sklad_2026-10-29_16-42-20.dump
```

На время восстановления `make container-restore` останавливает `app`, чтобы никто не менял данные, и запускает его снова. Перед восстановлением текущее состояние сохраняется в копию `before-restore`.

Скопировать файл копии из тома на компьютер и обратно:

```bash
docker compose cp app:/backups/sklad_2026-10-29_16-42-20.dump .
docker compose cp sklad_2026-10-29_16-42-20.dump app:/backups/
```

### Восстановление в новый том

Например, том с базой испорчен или удалён, а копия осталась в томе `backups`:

```bash
make container-backup                 # если база ещё жива — свежая копия
make down
docker volume rm sklad_db-data        # удалить старый том с базой
docker compose up -d --wait           # новый пустой том: initdb создаёт sklad, migrate — таблицы
docker compose stop app
docker compose run --rm app python -m app.cli restore --yes
docker compose start app
```

## 8. Ограничения ресурсов

| Сервис | CPU | Память | Замер (`docker stats`) | Обоснование |
|---|---|---|---|---|
| `app` | 0.5 | 256 МБ | простой: ~65 МиБ; нагрузка 3000 запросов в 30 потоков: ~75 МиБ, CPU упирается в 0.5 | один процесс uvicorn; 0.5 CPU — ~160 запросов `/health` в секунду, для склада с несколькими пользователями с большим запасом; память — запас в 3 раза на большие списки и резервное копирование (`pg_dump` запускается в контейнере `app`) |
| `migrate` | 0.5 | 256 МБ | работает несколько секунд при запуске | тот же образ и те же требования, что у `app` |
| `db` | 1.0 | 512 МБ | простой: ~40 МиБ; под нагрузкой ~55 МиБ | `shared_buffers` по умолчанию 128 МБ + память на подключения (их не больше 20) и запросы; база учебная и небольшая |

Ограничения не дают одному контейнеру занять всю память и процессор компьютера: при утечке памяти контейнер будет перезапущен (`restart: unless-stopped`), а не «положит» систему.

Повторить замер:

```bash
# в одном окне — нагрузка
.venv/bin/python -c "import urllib.request as u, concurrent.futures as f; list(f.ThreadPoolExecutor(30).map(lambda _: u.urlopen('http://127.0.0.1:8080/health').read(), range(3000)))"
# в другом — потребление
docker stats --no-stream
```

(на Windows вместо `.venv/bin/python` — `.venv\Scripts\python`).

## 9. Обновление базового образа и зависимостей

```bash
docker pull python:3.13-slim-trixie
docker run --rm python:3.13-slim-trixie python --version          # например, 3.13.9
docker pull python:3.13.9-slim-trixie
docker image inspect --format "{{index .RepoDigests 0}}" python:3.13.9-slim-trixie
```

Полученный digest подставить в `ARG PYTHON_IMAGE` в `Dockerfile` (для PostgreSQL — `image` сервиса `db` в `compose.yaml`; мажорная версия PostgreSQL при этом не меняется — файлы базы 17 не открываются сервером 18). После изменения `requirements.txt` нужно обновить `requirements-lock.txt` — порядок описан в комментарии в начале файла. Затем пересобрать образ (`make up`) и выполнить `make verify`.

## 10. Неполадки

| Сообщение | Причина и решение |
|---|---|
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop не запущен — запустить и дождаться «Engine running» |
| `нет SKLAD_DB_PASSWORD в .env — выполните make setup` | в `.env` нет паролей для контейнеров — `make setup` их допишет |
| `Bind for 127.0.0.1:8080 failed: port is already allocated` | порт занят — указать другой в `.env`: `SKLAD_PORT=8081` |
| `password authentication failed for user "sklad"` | пароль в `.env` поменяли после создания тома (раздел 4) |
| `dependency failed to start: container sklad-migrate-1 exited (1)` | ошибка миграции: `docker compose logs migrate` |
| контейнер `app` `unhealthy` | `docker compose logs app`; `docker inspect --format "{{json .State.Health}}" sklad-app-1` |
