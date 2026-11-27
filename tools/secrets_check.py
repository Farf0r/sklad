"""Поиск секретов в файлах проекта (make secrets, этап CI «Безопасность кода»).

Проверяются файлы репозитория и новые файлы, ещё не добавленные в Git (игнорируемые —
.env, .venv и т. п. — не проверяются). Сканер detect-secrets ищет ключи и токены известных
сервисов (AWS, GitHub, Slack, закрытые ключи и др.), пароли в строках подключения и
присваиваниях, строки с высокой энтропией.

Найденное сравнивается с .secrets.baseline — списком проверенных ложных срабатываний
(примеры паролей в образцах настроек, тестовые пароли). Любая новая находка — ошибка.
Если находка действительно не секрет, её вносят в список командой make secrets-baseline,
указав файл и строку. Изменение .secrets.baseline видно в запросе на слияние.
"""

import argparse
import json
import os
import subprocess  # nosec B404 — получение списка файлов проекта
import sys
from pathlib import Path

from detect_secrets import SecretsCollection
from detect_secrets.core import baseline

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ".secrets.baseline"
REPORT = ROOT / "reports" / "secrets.json"


def project_files() -> list[str]:
    result = subprocess.run(  # nosec B603, B607 — фиксированная команда без оболочки
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    files = [name for name in result.stdout.split("\0") if name and name != BASELINE]
    return [name for name in files if (ROOT / name).is_file()]


def posix(collection: SecretsCollection) -> SecretsCollection:
    """Пути с прямой косой чертой: список одинаково читается на Windows и в CI (Linux)."""
    result = SecretsCollection()
    for name, secret in collection:
        secret.filename = name.replace("\\", "/")
        result[secret.filename].add(secret)
    return result


def scan() -> SecretsCollection:
    found = SecretsCollection()
    found.scan_files(*project_files(), num_processors=min(os.cpu_count() or 1, 4))
    return posix(found)


def load_known() -> SecretsCollection:
    # настройки сканера (набор плагинов и фильтров) берутся из .secrets.baseline
    return posix(baseline.load(baseline.load_from_file(BASELINE), BASELINE))


def update_baseline(known: SecretsCollection, filename: str, line: int):
    """Добавляет одну находку после ручной проверки файла и строки."""
    name = Path(filename).as_posix()
    new = scan() - known
    candidates = [secret for path, secret in new if path == name and secret.line_number == line]
    if len(candidates) != 1:
        raise SystemExit("Укажите файл и строку с одной новой находкой из make secrets")
    secret = candidates[0]
    secret.is_secret = False
    known[name].add(secret)
    baseline.save_to_file(known, BASELINE)
    print(f"{BASELINE}: добавлено проверенное исключение {name}:{line}")


def main():
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow", nargs=2, metavar=("FILE", "LINE"))
    args = parser.parse_args()
    known = load_known()
    if args.allow:
        name, line = args.allow
        update_baseline(known, name, int(line))
        return
    found = scan()

    problems = [
        (name, secret)
        for name, secret in found
        if not any(item == secret and item.is_secret is False for item in known[name])
    ]
    problems.sort(key=lambda item: (item[0], item[1].line_number))

    REPORT.parent.mkdir(exist_ok=True)
    report = [{"file": name, "line": s.line_number, "type": s.type} for name, s in problems]
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    checked = len(project_files())
    if problems:
        print(f"Найдены возможные секреты ({len(problems)}):")
        for name, secret in problems:
            print(f"  {name}:{secret.line_number}  {secret.type}")
        print(
            "\nУберите секрет из файла и смените его: он мог уже попасть в историю Git "
            "(CONTRIBUTING.md, раздел 10).\nЕсли это не секрет (пример или тестовое значение), "
            "внесите его в список: make secrets-baseline FILE=путь LINE=номер"
        )
        sys.exit(1)
    print(f"Секретов не найдено: проверено файлов — {checked}")


if __name__ == "__main__":
    main()
