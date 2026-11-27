ifeq ($(OS),Windows_NT)
    PYTHON ?= python
    VENV_PY = ".venv/Scripts/python.exe"
else
    PYTHON ?= python3
    VENV_PY = .venv/bin/python
endif

.PHONY: setup run migrate backup restore test quality sast rules format verify mutation createadmin \
	up down container-migrate container-backup container-restore container-createadmin \
	container-check migrations-check backup-check image ci \
	secrets secrets-baseline deps image-scan tests-guard

# первоначальная настройка: окружение, зависимости, файлы .env и .env.test
setup:
	$(PYTHON) -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements-dev.txt
	$(VENV_PY) tools/init_env.py

run:
	$(VENV_PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

migrate:
	$(VENV_PY) -m app.cli migrate

# резервная копия базы из .env в каталог backups/
backup:
	$(VENV_PY) -m app.cli backup

# make restore — из последней копии, make restore FILE=backups/имя.dump — из указанной
restore:
	$(VENV_PY) -m app.cli restore $(FILE)

# тесты на тестовой базе из .env.test, отчёты в reports/
test:
	$(VENV_PY) -m pytest

# отчёты анализаторов пишутся в reports/ до проверки, чтобы сохраниться и при ошибках
quality:
	$(VENV_PY) -m ruff check . --exit-zero --output-format=json --output-file=reports/ruff.json
	$(VENV_PY) -m ruff check .
	$(VENV_PY) -m ruff format --check .

# поиск уязвимостей в коде (SAST)
sast:
	$(VENV_PY) -c "import os; os.makedirs('reports', exist_ok=True)"
	$(VENV_PY) -m bandit -q -c pyproject.toml -r app migrations tools --exit-zero -f json -o reports/bandit.json
	$(VENV_PY) -m bandit -c pyproject.toml -r app migrations tools

# поиск секретов в файлах проекта (detect-secrets): находки сверяются со списком
# проверенных ложных срабатываний .secrets.baseline
secrets:
	$(VENV_PY) -X utf8 -m tools.secrets_check

# внести текущие находки в .secrets.baseline — только если это точно не секреты
secrets-baseline:
	$(VENV_PY) -X utf8 -m tools.secrets_check --allow "$(FILE)" "$(LINE)"

# известные уязвимости в зависимостях (pip-audit); нужен интернет
deps:
	$(VENV_PY) -m tools.deps_check

# запрет пропуска тестов, снижения порогов и исключений без обоснования
rules:
	$(VENV_PY) tools/check_rules.py

TESTS_BASE ?= HEAD
tests-guard:
	$(VENV_PY) -X utf8 -m tools.tests_guard "$(TESTS_BASE)"

format:
	$(VENV_PY) -m ruff format .
	$(VENV_PY) -m ruff check --fix .

verify: rules tests-guard quality sast secrets test

# мутационное тестирование: тесты должны замечать ошибки в правилах приложения
mutation:
	$(VENV_PY) tools/mutate.py

createadmin:
	$(VENV_PY) -m app.cli create-user --username admin --role admin

# ---------- контейнерное окружение (docker compose, docs/docker.md) ----------

# собрать образ и запустить базу, миграции и приложение; ждёт, пока всё станет healthy.
# Окружение меняется только после успешной проверки make container-check.
up: container-check
	docker compose up -d --build --wait

# остановить и удалить контейнеры; тома с данными и резервными копиями остаются
down:
	docker compose down

container-migrate:
	docker compose run --rm migrate

container-backup:
	docker compose run --rm app python -m app.cli backup

# make container-restore — из последней копии, FILE=/backups/имя.dump — из указанной;
# на время восстановления приложение останавливается
container-restore:
	docker compose stop app
	-docker compose run --rm app python -m app.cli restore $(FILE)
	docker compose start app

container-createadmin:
	docker compose run --rm app python -m app.cli create-user --username admin --role admin

# проверка образа и контейнерного окружения в отдельном проекте sklad-check (порт 18080);
# рабочее окружение make up и его данные не затрагиваются
container-check:
	$(VENV_PY) tools/container_check.py

# ---------- проверки, которые выполняет CI (docs/ci.md) ----------

# миграции на тестовой базе: чистая база, откат и повторное применение, alembic check, обновление с данными
migrations-check:
	$(VENV_PY) -m tools.migrations_check

# резервная копия, порча данных и восстановление на тестовой базе
backup-check:
	$(VENV_PY) -m tools.backup_check

# образ приложения с тегом по коммиту: sklad:sha-<первые 7 символов SHA>
IMAGE_TAG ?= sha-$(shell git rev-parse --short=7 HEAD)
# метки связывают образ с коммитом и репозиторием; команда в одну строку — так она работает и в cmd.exe
IMAGE_LABELS = --label org.opencontainers.image.revision=$(shell git rev-parse HEAD) \
	--label org.opencontainers.image.source=https://github.com/Farf0r/sklad
image:
	docker build -t sklad:$(IMAGE_TAG) $(IMAGE_LABELS) .

# анализ образа сканером Trivy (tools/image_scan.py): уязвимости HIGH и CRITICAL, для которых
# есть исправление, запрещают публикацию; полный отчёт — reports/trivy.json
image-scan: image
	$(PYTHON) -m tools.image_scan sklad:$(IMAGE_TAG)

# локально то же, что CI, кроме публикации образа
ci: verify deps migrations-check backup-check container-check image-scan
