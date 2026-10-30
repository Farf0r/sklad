"""Автоматическая проверка контейнерного окружения (make container-check).

Сначала проверяются файлы: Dockerfile, .dockerignore и итоговая конфигурация Compose.
Затем поднимается отдельное проверочное окружение — проект sklad-check со своими томами
и портом 18080 — и в нём проверяется работа: пользователь процессов, healthcheck,
ограничения ресурсов, порты, отсутствие секретов в образе, миграции, корректное
завершение, сохранность данных при пересоздании контейнеров, резервная копия и
восстановление в новый том. Рабочее окружение (make up) и его данные не затрагиваются.
В конце проверочное окружение удаляется вместе с томами.
"""

import json
import os
import re
import subprocess  # nosec B404 — запуск команд контейнерного окружения из этого же скрипта
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "sklad-check"
PORT = "18080"
# строка-метка в справочнике единиц: по ней видно, сохранились ли данные
ADD_MARKER = "INSERT INTO units (name, short_name) VALUES ('container-check', 'cc')"
COUNT_MARKER = "SELECT count(*) FROM units WHERE name = 'container-check'"
SECRET_WORDS = ("PASSWORD", "SECRET", "TOKEN", "DATABASE_URL")


class CheckFailed(Exception):
    pass


# ---------- проверки файлов ----------


def image_pinned(ref: str) -> bool:
    """Образ задан точной версией и digest, без latest."""
    name, _, digest = ref.partition("@")
    tag = name.rpartition(":")[2] if ":" in name.rpartition("/")[2] else ""
    return tag not in ("", "latest") and re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is not None


def dockerfile_problems(text: str) -> list[str]:
    problems = []
    # инструкция может продолжаться на следующих строках после «\»
    text = re.sub(r"\\\s*\n\s*", " ", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    args, bases = {}, []
    for line in lines:
        word, _, rest = line.partition(" ")
        word = word.upper()
        if word == "ARG" and "=" in rest:
            name, value = rest.split("=", 1)
            args[name] = value
        if word == "FROM":
            ref = rest.split()[0]
            bases.append(args.get(ref.strip("${}"), ref))
        if word in ("ENV", "ARG") and any(w in rest.upper() for w in SECRET_WORDS):
            problems.append(f"в Dockerfile секрет в {word}: {line}")
    for ref in dict.fromkeys(bases):
        if not image_pinned(ref):
            problems.append(f"базовый образ не закреплён версией и digest: {ref}")
    users = [line.split(None, 1)[1] for line in lines if line.upper().startswith("USER ")]
    if not users or users[-1].split(":")[0] in ("root", "0"):
        problems.append("в Dockerfile нет USER с непривилегированным пользователем")
    health = [line for line in lines if line.upper().startswith("HEALTHCHECK")]
    if not health or health[-1].upper().startswith("HEALTHCHECK NONE"):
        problems.append("в Dockerfile нет HEALTHCHECK")
    cmd = [line for line in lines if line.upper().startswith(("CMD", "ENTRYPOINT"))]
    if not cmd or not cmd[-1].split(None, 1)[1].startswith("["):
        problems.append("CMD не в exec-форме: процесс не получит сигнал остановки")
    return problems


def dockerignore_problems(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    if not lines or lines[0] != "*":
        return [".dockerignore должен начинаться с * и перечислять только нужное (!app/ ...)"]
    allowed = [line for line in lines if line.startswith("!")]
    leaked = [line for line in allowed if ".env" in line or "backup" in line or ".git" in line]
    return [f".dockerignore пропускает в образ лишнее: {line}" for line in leaked]


def compose_problems(config: dict, version: str) -> list[str]:
    problems = []
    services = config.get("services", {})
    # образ приложения собирается из Dockerfile, digest есть только у скачанных образов
    built = {service.get("image") for service in services.values() if "build" in service}
    for name, service in services.items():
        image = service.get("image", "")
        tag = image.split("@")[0].rpartition(":")[2] if ":" in image else ""
        if not tag or tag == "latest":
            problems.append(f"{name}: образ без точного тега или latest: {image!r}")
        if image not in built and not image_pinned(image):
            problems.append(f"{name}: сторонний образ не закреплён digest: {image}")
        if str(service.get("user", "")).split(":")[0] in ("root", "0"):
            problems.append(f"{name}: запуск от root")
        health = service.get("healthcheck", {})
        if health.get("disable") or health.get("test") in (["NONE"], "NONE"):
            problems.append(f"{name}: healthcheck отключён")
        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        if not limits.get("cpus") or not limits.get("memory"):
            problems.append(f"{name}: не заданы ограничения cpus и memory")
        for port in service.get("ports", []):
            if name != "app":
                problems.append(f"{name}: опубликован порт {port.get('published')}")
            elif port.get("host_ip") != "127.0.0.1":
                problems.append("app: порт опубликован не только для 127.0.0.1")
    if services.get("app", {}).get("image", "").split(":")[-1] != version:
        problems.append(f"тег образа приложения не совпадает с версией {version}")
    if "healthcheck" not in services.get("db", {}):
        problems.append("db: нет healthcheck")
    db_volumes = services.get("db", {}).get("volumes", [])
    data = [v for v in db_volumes if v.get("target") == "/var/lib/postgresql/data"]
    if not data or data[0].get("type") != "volume":
        problems.append("db: данные не в именованном томе")
    if not config.get("networks", {}).get("backend", {}).get("internal"):
        problems.append("сеть backend должна быть internal")
    return problems


# ---------- запуск docker ----------


def env() -> dict:
    return {**os.environ, "SKLAD_PORT": PORT}


def run(args: list[str], check=True, timeout=600) -> str:
    result = subprocess.run(  # nosec B603 — список аргументов без оболочки
        args,
        cwd=ROOT,
        env=env(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
        raise CheckFailed(f"команда {' '.join(args)} завершилась с ошибкой:\n" + "\n".join(tail))
    return result.stdout


def compose(*args: str, **kw) -> str:
    return run(["docker", "compose", "-p", PROJECT, *args], **kw)


def inspect(container: str) -> dict:
    return json.loads(run(["docker", "inspect", container]))[0]


def container_id(service: str) -> str:
    return compose("ps", "-q", service).strip()


def psql(sql: str) -> str:
    return compose(
        "exec", "-T", "db", "psql", "-U", "postgres", "-d", "sklad", "-tA", "-c", sql
    ).strip()


def marker_count() -> int:
    return int(psql(COUNT_MARKER))


def app_version() -> str:
    text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def head_revision() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()


# ---------- ход проверки ----------

step_no = 0


def step(text: str):
    global step_no
    step_no += 1
    print(f"{step_no:2}. {text}", flush=True)


def ok(text: str):
    print(f"      ok  {text}", flush=True)


def require(condition: bool, text: str):
    if not condition:
        raise CheckFailed(text)
    ok(text)


def check_files(version: str):
    step("Dockerfile, .dockerignore и конфигурация Compose")
    problems = dockerfile_problems((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    problems += dockerignore_problems((ROOT / ".dockerignore").read_text(encoding="utf-8"))
    config = json.loads(compose("config", "--format", "json"))
    problems += compose_problems(config, version)
    if problems:
        raise CheckFailed("нарушены правила:\n" + "\n".join(f"  - {p}" for p in problems))
    ok("образы с точными версиями и digest, без latest; USER не root; HEALTHCHECK есть")
    ok("секретов в Dockerfile нет; в контекст сборки попадает только код приложения")
    ok("ограничения cpus и memory у всех сервисов; порт только у app и только 127.0.0.1")


def check_environment(version: str):
    step("Сборка образа и запуск проверочного окружения")
    compose("down", "-v", "--remove-orphans", check=False)
    compose("up", "-d", "--build", "--wait", timeout=900)
    app, db = container_id("app"), container_id("db")
    ok(f"проект {PROJECT}: db, migrate, app запущены")

    step("Пользователь процессов")
    app_uid = compose("exec", "-T", "app", "id", "-u").strip()
    require(app_uid not in ("", "0"), f"приложение работает от uid {app_uid}, не root")
    db_uid = compose("exec", "-T", "db", "awk", "/^Uid/{print $2}", "/proc/1/status").strip()
    require(db_uid not in ("", "0"), f"PostgreSQL работает от uid {db_uid}, не root")

    step("Healthcheck, ограничения ресурсов, порты")
    for name, cid in (("app", app), ("db", db)):
        info = inspect(cid)
        health = info["State"].get("Health", {}).get("Status")
        require(health == "healthy", f"{name}: healthcheck {health}")
        host = info["HostConfig"]
        require(host["Memory"] > 0 and host["NanoCpus"] > 0, f"{name}: ограничения памяти и CPU")
    db_ports = inspect(db)["HostConfig"]["PortBindings"] or {}
    require(not db_ports, "порт базы данных не опубликован")
    url = f"http://127.0.0.1:{PORT}/health"
    with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310 — адрес задан в коде
        health = json.load(response)
    require(health == {"status": "ok", "db": "ok", "version": version}, f"/health: {health}")

    step("Секреты не попали в образ")
    image = inspect(app)["Config"]["Image"]
    image_env = json.loads(run(["docker", "image", "inspect", image]))[0]["Config"]["Env"]
    leaked = [item.split("=")[0] for item in image_env if any(w in item for w in SECRET_WORDS)]
    require(not leaked, f"в переменных образа {image} нет паролей и ключей")
    files = run(["docker", "run", "--rm", "--entrypoint", "ls", image, "-A", "/app"]).split()
    require(
        not any(f.startswith(".env") or f in (".git", "tests", "backups") for f in files),
        f"в /app только код: {' '.join(sorted(files))}",
    )

    step("Миграции в контейнере")
    out = compose("run", "--rm", "migrate")
    require("Схема базы данных актуальна" in out, "миграции выполнены повторно без ошибок")
    revision = psql("SELECT version_num FROM alembic_version")
    require(revision == head_revision(), f"версия схемы {revision} — последняя")

    step("Корректное завершение по сигналу остановки")
    started = time.monotonic()
    compose("stop", "-t", "20", "app")
    seconds = time.monotonic() - started
    state = inspect(app)["State"]
    require(state["ExitCode"] == 0, f"код завершения {state['ExitCode']} (не 137 — не убит)")
    require(seconds < 15, f"остановка заняла {seconds:.1f} с")
    logs = compose("logs", "--no-log-prefix", "app")
    require("Склад остановлен" in logs, "в журнале «Склад остановлен»: приложение закрылось само")
    compose("up", "-d", "--wait")

    step("Сохранность данных при пересоздании контейнеров")
    psql(ADD_MARKER)
    compose("up", "-d", "--force-recreate", "--wait")
    require(container_id("app") != app, "контейнеры пересозданы")
    require(marker_count() == 1, "данные в томе сохранились")

    step("Резервная копия и восстановление в новый том")
    out = compose("run", "--rm", "app", "python", "-m", "app.cli", "backup")
    require("Резервная копия создана" in out, "резервная копия создана")
    compose("down")
    run(["docker", "volume", "rm", f"{PROJECT}_db-data"])
    compose("up", "-d", "--wait")
    require(marker_count() == 0, "новый том базы пустой: данных нет")
    compose("stop", "app")
    out = compose("run", "--rm", "app", "python", "-m", "app.cli", "restore", "--yes")
    require("База восстановлена" in out, "база восстановлена из копии")
    compose("up", "-d", "--wait")
    require(marker_count() == 1, "данные вернулись в новый том")


def main():
    keep = "--keep" in sys.argv
    version = app_version()
    print(f"Проверка контейнерного окружения, версия приложения {version}\n")
    try:
        check_files(version)
        check_environment(version)
    except CheckFailed as exc:
        print(f"\nПРОВЕРКА НЕ ПРОЙДЕНА: {exc}")
        code = 1
    except FileNotFoundError:
        print("\nПРОВЕРКА НЕ ПРОЙДЕНА: не найдена команда docker — установите и запустите Docker")
        code = 1
    else:
        print("\nКонтейнерное окружение соответствует требованиям")
        code = 0
    finally:
        if not keep:
            compose("down", "-v", "--remove-orphans", check=False)
    sys.exit(code)


if __name__ == "__main__":
    main()
