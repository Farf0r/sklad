# Тестирование и проверки

## Состав make verify

`make verify` — обязательный набор проверок перед каждым запросом на слияние. Шаги выполняются по порядку, любая ошибка останавливает проверку.

| Шаг | Команда | Что проверяет |
|---|---|---|
| `make rules` | `python tools/check_rules.py` | правила проекта: нет пропущенных тестов (`skip`, `xfail`), порог покрытия не ниже 95 %, правила ruff не отключены, у bandit нет отключённых проверок, `make verify` содержит все шаги, у каждого исключения `noqa` / `nosec` есть код правила и причина |
| `make quality` | `ruff check .` и `ruff format --check .` | стиль кода и типичные ошибки (линтер), единое форматирование |
| `make sast` | `bandit -c pyproject.toml -r app migrations tools` | статический анализ безопасности (SAST): опасные вызовы, пароли в коде, SQL-инъекции и т. п. |
| `make test` | `pytest` | unit-, API- и интеграционные тесты на тестовой базе PostgreSQL, покрытие кода (не ниже 95 %), отчёты |

Отдельно, перед изменением правил предметной области, запускается `make mutation` — мутационное тестирование (ниже).

## Тестовая база

Тесты работают только с отдельной базой PostgreSQL, рабочая база из `.env` не используется.

1. Создать базу (один раз, в «SQL Shell (psql)» под пользователем `postgres`):

   ```sql
   CREATE DATABASE sklad_test OWNER sklad;
   ```

2. Скопировать `.env.test.example` в `.env.test` и вписать пароль пользователя `sklad` — это делает `make setup`, если файла ещё нет. Файл `.env.test` в репозиторий не попадает.

Имя базы обязано оканчиваться на `_test`: перед первым тестом, которому нужна база, все таблицы в ней удаляются и схема создаётся заново миграциями (`tests/conftest.py`), а перед каждым API- и интеграционным тестом таблицы очищаются. Поэтому тесты не зависят от порядка запуска и от данных друг друга. Если `TEST_DATABASE_URL` не задана или указывает на другую базу, тесты не запускаются.

Unit-тесты (`tests/unit/`) к базе не подключаются: `pytest tests/unit` проходит, даже если PostgreSQL остановлен. Если при проблеме с подключением unit-тесты проходят, а остальные падают с `OperationalError`, дело в базе или в `.env.test`, а не в коде.

## Структура тестов

| Каталог | Что проверяет | База |
|---|---|---|
| `tests/unit/` | основную логику без базы: проверку входных данных и граничные значения, расчёт сумм и округление, ввод чисел с запятой, сообщения об ошибках, хеширование паролей | не нужна |
| `tests/api/` | функции системы через HTTP API и веб-страницы: справочники, поступления и их проведение, права ролей, ошибки 401/403/404/409/422/500, `/health` | тестовая |
| `tests/integration/` | работу с базой данных: миграции на чистой и заполненной базе, откат каждой миграции, соответствие моделей и миграций, ограничения CHECK / UNIQUE / FK на уровне БД, одновременное проведение поступления, резервное копирование и восстановление после порчи данных, консольные команды | тестовая |

## Отчёты

После `make test` в каталоге `reports/` (в репозиторий не попадает):

| Файл | Что внутри |
|---|---|
| `reports/coverage/index.html` | покрытие кода по файлам и строкам, открывается в браузере |
| `reports/coverage.xml` | покрытие в формате Cobertura (для CI в ЛР5) |
| `reports/junit.xml` | результаты тестов в формате JUnit (для CI в ЛР5) |

Краткий отчёт о покрытии печатается в конце `make test`; при покрытии ниже 95 % проверка не проходит.

## Покрытие требований ТЗ

| Требование ТЗ | Тесты |
|---|---|
| ФТ-1 Вход и выход | `api/test_auth.py`, `api/test_web_pages.py::test_logout_page`, `api/test_errors.py::test_wrong_password_on_login_page` |
| ФТ-2 Текущий пользователь | `api/test_auth.py::test_login_and_me`, `test_me_without_login_returns_401` |
| ФТ-3 Единицы измерения | `api/test_units.py`, `api/test_web_pages.py::test_units_pages`, `unit/test_schemas.py::test_unit_rejected` |
| ФТ-4 Материалы | `api/test_materials.py`, `api/test_web_pages.py::test_materials_pages`, `unit/test_schemas.py::test_material_has_no_stock_field` |
| ФТ-5 Поставщики | `api/test_suppliers.py`, `api/test_web_pages.py::test_suppliers_pages`, `unit/test_schemas.py` (ИНН, email) |
| ФТ-6 Черновик поступления | `api/test_receipts.py::test_create_receipt_is_draft`, `test_unknown_supplier_and_material` |
| ФТ-7 Строки поступления | `api/test_receipts.py::test_add_and_remove_item`, `unit/test_logic.py` (суммы и итог) |
| ФТ-8 Проведение поступления | `api/test_receipts.py::test_post_receipt_increases_stock`, `test_stock_accumulates_over_receipts`, `integration/test_concurrency.py` |
| ФТ-9 Список поступлений | `api/test_receipts.py::test_filter_by_status` |
| ФТ-10 Удаление | `api/test_*.py::test_only_admin_*`, `api/test_web_pages.py::test_storekeeper_cannot_delete_from_pages` |
| ФТ-11 Проверка работоспособности | `api/test_health.py`, `api/test_errors.py::test_health_when_database_is_down` |
| ФТ-14 Минимальный остаток, список «К заказу» | `api/test_min_stock.py`, `unit/test_min_stock.py`, `integration/test_migrations.py::test_upgrade_keeps_existing_data` |
| ПР-1 Остаток только при проведении | `api/test_materials.py::test_new_material_has_zero_stock_even_if_sent`, `api/test_receipts.py::test_draft_does_not_change_stock` |
| ПР-2 Провести можно только черновик со строками | `api/test_receipts.py::test_cannot_post_twice`, `test_cannot_post_empty_receipt` |
| ПР-3 Проведённое нельзя изменить | `api/test_receipts.py::test_posted_receipt_is_read_only` |
| ПР-4 Количество > 0, цена ≥ 0, материал один раз | `unit/test_schemas.py` (границы), `api/test_receipts.py::test_same_material_twice`, `integration/test_constraints.py` |
| ПР-5 Нельзя удалить используемое | `api/test_units.py::test_cannot_delete_unit_used_by_material`, `api/test_receipts.py::test_cannot_delete_supplier_or_material_with_receipts`, `api/test_materials.py::test_material_with_fractional_stock_cannot_be_deleted` |
| ПР-6 Удаляет только администратор | `api/test_*.py::test_only_admin_*` |
| ПР-7 Уникальность, формат ИНН | `unit/test_schemas.py::test_inn_*`, `api/test_suppliers.py::test_duplicate_inn` |
| ПР-8 Заказ, если остаток меньше минимального; минимальный остаток ≥ 0 | `unit/test_min_stock.py` (границы: равно, чуть меньше, чуть больше), `api/test_min_stock.py::test_filter_materials_to_order`, `integration/test_constraints.py` |

Тестами покрыты все 12 реализованных функций и все 8 правил из ТЗ (ФТ-12 и ФТ-13 в ТЗ запланированы на следующие версии), то есть 20 из 22 требований — 91 % (по заданию нужно не меньше 40 %).

## Мутационное тестирование

`make mutation` (`tools/mutate.py`) по очереди вносит в код намеренную ошибку — меняет условие, знак или границу в правилах предметной области — и запускает тесты. Тесты должны упасть («мутант убит»). Если тесты прошли («мутант выжил»), правило не проверяется и нужен новый тест. После каждой мутации файл возвращается в исходный вид.

При первом запуске выжили 4 мутанта из 13: удаление проверок в коде не замечалось, потому что запрос всё равно отклоняла база данных (ограничения UNIQUE и внешние ключи), и тест видел тот же код 409. Тесты усилены: теперь они проверяют не только код ответа, но и текст ошибки от правила приложения. После этого убиты все 13 мутантов.

С функцией «минимальный остаток» добавлены ещё 5 мутантов (граница `<` / `<=` в модели и в запросе, отрицательная нехватка, отрицательный минимальный остаток, минимальный остаток не сохраняется при изменении). Убиты все 18.

С резервным копированием добавлены 2 мутанта: восстановление без подтверждения и выбор копии `before-restore` как последней. Первый выжил: тест отмены отвечал «no», а мутант отменял восстановление только на «no» и пропускал любой другой ответ. Тест переписан на несколько ответов (`no`, пустая строка, `y`, `да`). Сейчас убиты все 20 мутантов.

Распространённый инструмент mutmut работает только в системах с fork, под Windows — только через WSL, поэтому используется собственный короткий скрипт с фиксированным списком мутаций в правилах приложения.
