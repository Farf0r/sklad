ifeq ($(OS),Windows_NT)
    PYTHON ?= python
    VENV_PY = ".venv/Scripts/python.exe"
else
    PYTHON ?= python3
    VENV_PY = .venv/bin/python
endif

.PHONY: setup run migrate backup restore test quality sast rules format verify mutation createadmin \
	up down container-migrate container-backup container-restore container-createadmin

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

quality:
	$(VENV_PY) -m ruff check .
	$(VENV_PY) -m ruff format --check .

# поиск уязвимостей в коде (SAST)
sast:
	$(VENV_PY) -m bandit -c pyproject.toml -r app migrations tools

# запрет пропуска тестов, снижения порогов и исключений без обоснования
rules:
	$(VENV_PY) tools/check_rules.py

format:
	$(VENV_PY) -m ruff format .
	$(VENV_PY) -m ruff check --fix .

verify: rules quality sast test

# мутационное тестирование: тесты должны замечать ошибки в правилах приложения
mutation:
	$(VENV_PY) tools/mutate.py

createadmin:
	$(VENV_PY) -m app.cli create-user --username admin --role admin

# ---------- контейнерное окружение (docker compose, docs/docker.md) ----------

# собрать образ и запустить базу, миграции и приложение; ждёт, пока всё станет healthy
up:
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
