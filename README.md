# Склад — система складского учёта

Учебный проект по дисциплине «DevOps», Московский Политех.
Веб-приложение для учёта материалов, единиц измерения, поставщиков и поступлений на склад.

## Команда

| Участник | Зона ответственности |
|---|---|
| Денис Третьяков ([@Farf0r](https://github.com/Farf0r)) | каркас, авторизация, единицы измерения, материалы |
| Иван Петров ([@ivan-11-p](https://github.com/ivan-11-p)) | поставщики, поступления |

## Возможности (v0.3.0)

- вход по логину и паролю, роли «администратор» и «кладовщик»;
- справочники: единицы измерения, материалы, поставщики;
- поступления на склад: черновик → строки (материал, количество, цена) → проведение;
- минимальный остаток материала и список «К заказу»: материалы, которых осталось меньше минимума;
- HTTP API в формате JSON и веб-интерфейс;
- служебный адрес `/health`, журнал запросов и ошибок.
- развёртывание на двух серверах Debian 13: приложение как systemd-служба, PostgreSQL на отдельной машине и доступен только серверу приложения.

## Правила предметной области

1. Остаток материала нельзя задать вручную: он увеличивается только при **проведении поступления**.
2. Провести можно только черновик, в котором есть хотя бы одна строка. Все остатки обновляются в одной транзакции, одновременное повторное проведение блокируется.
3. Проведённое поступление нельзя изменить или удалить.
4. Количество в строке больше 0, цена не меньше 0, один материал встречается в поступлении один раз.
5. Нельзя удалить единицу измерения, материал или поставщика, если на них ссылаются другие записи; нельзя удалить материал с ненулевым остатком.
6. Удалять записи может только администратор.
7. ИНН поставщика: 10 или 12 цифр; названия и ИНН уникальны.
8. Материал нужно заказать, если его остаток **меньше** минимального. Минимальный остаток не меньше 0; 0 — не отслеживать.

## Стек

Python 3.12+, FastAPI, SQLAlchemy 2, PostgreSQL 16+, Jinja2, pytest, ruff. На сервере: Debian 13, systemd, ufw.

## Быстрый старт

Нужны: Python 3.12+, PostgreSQL 16, Git и GNU make (на Windows: `winget install ezwinports.make`).

1. Создайте пользователя, рабочую и тестовую базы (Windows: «SQL Shell (psql)» из меню Пуск, вход под `postgres`):

   ```sql
   CREATE USER sklad WITH PASSWORD 'придумайте-пароль';
   CREATE DATABASE sklad OWNER sklad;
   CREATE DATABASE sklad_test OWNER sklad;
   ```

2. Первоначальная настройка — одна команда:

   ```bash
   make setup
   ```

   Она создаёт виртуальное окружение `.venv`, ставит зависимости с зафиксированными версиями (`requirements*.txt`) и, если их ещё нет, файлы настроек `.env` и `.env.test` из образцов: спрашивает пароль пользователя `sklad` и генерирует `SECRET_KEY`.

3. Создайте таблицы в базе (применить миграции):

   ```bash
   make migrate
   ```

4. Создайте администратора (пароль спросит в консоли, не короче 8 символов):

   ```bash
   make createadmin
   ```

5. Запустите приложение:

   ```bash
   make run
   ```

   Веб-интерфейс: http://127.0.0.1:8000, Swagger: http://127.0.0.1:8000/docs, проверка работоспособности: http://127.0.0.1:8000/health.

6. Проверьте, что всё работает: `make verify`.

Схема БД создаётся и изменяется только миграциями Alembic (`migrations/versions/`). После `git pull` с новыми миграциями выполните `make migrate`.

## Команды

| Команда | Что делает |
|---|---|
| `make setup` | первоначальная настройка: окружение `.venv`, зависимости, файлы `.env` и `.env.test` |
| `make run` | запускает приложение локально с автоперезагрузкой |
| `make migrate` | применяет миграции: приводит схему БД к последней версии |
| `make backup` | резервная копия базы из `.env` в каталог `backups/` |
| `make restore` | восстановление базы из последней копии (`make restore FILE=backups/имя.dump` — из указанной) |
| `make test` | автотесты на тестовой базе PostgreSQL с отчётом о покрытии (`reports/`) |
| `make quality` | проверка стиля и статический анализ (ruff) |
| `make sast` | поиск уязвимостей в коде (bandit) |
| `make rules` | проверка правил проекта: тесты не пропущены, пороги не снижены |
| `make format` | автоматически исправляет форматирование |
| `make verify` | **все обязательные проверки**: `rules` + `quality` + `sast` + `test` |
| `make mutation` | мутационное тестирование: тесты должны замечать ошибки в правилах |
| `make createadmin` | создаёт пользователя-администратора |

Кладовщика можно создать так: `python -m app.cli create-user --username ivanov --role storekeeper`.

<details>
<summary>Те же команды без make (Windows, PowerShell)</summary>

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

uvicorn app.main:app --reload            # make run
python -m app.cli migrate                # make migrate
python -m app.cli backup                 # make backup
python -m app.cli restore                # make restore
pytest                                   # make test
ruff check . ; ruff format --check .     # make quality
bandit -c pyproject.toml -r app migrations tools   # make sast
python tools/check_rules.py              # make rules
python -m app.cli create-user --username admin --role admin
```

Если PowerShell не даёт активировать окружение: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
</details>

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `DATABASE_URL` | да | строка подключения: `postgresql+psycopg://user:password@host:5432/db` |
| `SECRET_KEY` | да | ключ подписи cookie сессии, не короче 16 символов |
| `APP_ENV` | нет | `dev`, `test` или `prod` (по умолчанию `dev`) |
| `LOG_LEVEL` | нет | `DEBUG`, `INFO`, `WARNING`, `ERROR` (по умолчанию `INFO`) |
| `LOG_FILE` | нет | путь к файлу журнала; если не задан, журнал пишется только в консоль |
| `SESSION_MAX_AGE` | нет | время жизни сессии в секундах (по умолчанию 8 часов) |
| `BCRYPT_ROUNDS` | нет | сложность хеширования паролей (по умолчанию 12) |
| `BACKUP_DIR` | нет | каталог резервных копий (по умолчанию `backups`) |

Настройки читаются из переменных окружения или из файла `.env`. Файл `.env` содержит пароли и **не попадает в Git** (см. `.gitignore`); в репозитории лежит только образец `.env.example`.

## Журнал

Каждый запрос пишется одной строкой: время, уровень, модуль, идентификатор запроса, метод, адрес, код ответа и длительность.

```
2026-10-16 14:51:57,725 INFO    app.requests [c517de0126d5] POST /api/receipts/1/post -> 200 (40 мс)
```

Идентификатор запроса возвращается клиенту в заголовке `X-Request-ID` и в ответе с кодом 500, по нему ошибку легко найти в журнале. Пароли в журнал не пишутся.

## Тесты

Тесты работают на отдельной базе PostgreSQL `sklad_test`, рабочая база из `.env` не используется. Один раз:

1. Создайте базу («SQL Shell (psql)», вход под `postgres`): `CREATE DATABASE sklad_test OWNER sklad;`
2. Создайте файл `.env.test` по образцу `.env.test.example` и впишите пароль пользователя `sklad` (`make setup` делает это сам, если файла ещё нет).

Структура тестов, состав `make verify`, отчёты, покрытие требований ТЗ и мутационное тестирование — в [docs/testing.md](docs/testing.md).

## Резервное копирование

`make backup` сохраняет всю базу (схему и данные) одним файлом в `backups/`, `make restore` возвращает базу к состоянию из копии; перед восстановлением текущее состояние тоже сохраняется. Нужны утилиты PostgreSQL `pg_dump` и `pg_restore`: под Windows они ставятся вместе с PostgreSQL и находятся автоматически. Подробно — в [docs/backup.md](docs/backup.md).

## Развёртывание на сервере

Приложение разворачивается без контейнеров на двух машинах Debian 13: `sklad-app` (приложение как systemd-служба `sklad`) и `sklad-db` (PostgreSQL). Подробная инструкция, требования к эксплуатации и команды проверки — в [docs/deploy.md](docs/deploy.md).

Кратко, после установки ОС, настройки сети и SSH-ключей:

```bash
# на обеих машинах
sudo bash deploy/scripts/base-setup.sh
# на sklad-db
sudo bash deploy/scripts/db-setup.sh
# на sklad-app (репозиторий склонирован в /opt/sklad)
sudo bash /opt/sklad/deploy/scripts/app-setup.sh
sudo sklad-cli create-user --username admin --role admin
# проверка требований на каждой машине
sudo bash deploy/scripts/check.sh
```

Настройки сервера хранятся в `/etc/sklad/sklad.env` и в репозиторий не попадают; образец — `deploy/sklad.env.example`.

## Структура проекта

```
app/
  main.py            сборка приложения: middleware, обработчики ошибок, роутеры
  config.py          настройки из переменных окружения
  database.py        подключение к БД
  migrate.py         применение миграций
  backup.py          резервная копия и восстановление (pg_dump / pg_restore)
  logging_config.py  формат журнала
  middleware.py      журнал запросов и X-Request-ID
  errors.py          ошибки приложения и их перевод в HTTP-ответы
  security.py        пароли и проверка входа
  models/            таблицы БД (SQLAlchemy)
  schemas/           проверка входных данных и формат ответов (Pydantic)
  services/          бизнес-логика и правила предметной области
  routers/           адреса API (/api/...) и веб-страниц
  templates/         HTML-шаблоны
migrations/          миграции схемы БД (Alembic), alembic.ini — их настройки
tests/               автотесты: unit/, api/, integration/
tools/               настройка .env, проверка правил проекта, мутационное тестирование
docs/                описание API, схема данных, тесты, резервные копии, развёртывание
Dockerfile           образ приложения
.dockerignore        что попадает в контекст сборки образа (только код)
requirements-lock.txt  точные версии всех пакетов для образа
deploy/
  sklad.service      systemd-служба приложения
  sklad.env.example  образец настроек сервера
  scripts/           скрипты настройки серверов, обновления и проверки
```

## Документация

- [Описание API](docs/api.md), интерактивно: `/docs`
- [Схема данных](docs/schema.md)
- [Тестирование и проверки](docs/testing.md)
- [Резервное копирование и восстановление](docs/backup.md)
- [Развёртывание на Linux-серверах](docs/deploy.md)
- [Контейнерное окружение](docs/docker.md)
- [Правила внесения изменений](CONTRIBUTING.md)
