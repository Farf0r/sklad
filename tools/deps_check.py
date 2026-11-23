"""Проверка зависимостей на известные уязвимости (make deps, этап CI «Безопасность кода»).

pip-audit сверяет версии пакетов с базой уязвимостей PyPI (PyPA Advisory Database, OSV):
1. requirements-lock.txt — точные версии всех пакетов, которые попадают в образ приложения;
2. пакеты виртуального окружения .venv — приложение и инструменты разработки и проверок.

Любая известная уязвимость — ошибка: пакет обновляется до версии с исправлением
(она указана в выводе), затем make verify и make container-check. Отчёты — reports/deps-*.json.
Нужен доступ в интернет к pypi.org.
"""

import json
import subprocess  # nosec B404 — запуск сканера зависимостей из этого же окружения
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
AUDITS = {
    "образ приложения (requirements-lock.txt)": (
        "deps-image.json",
        ["-r", "requirements-lock.txt", "--no-deps", "--disable-pip"],
    ),
    "окружение разработки (.venv)": ("deps-dev.json", ["--skip-editable"]),
}


def audit(report: str, args: list[str]) -> list[str]:
    path = REPORTS / report
    path.unlink(missing_ok=True)
    result = subprocess.run(  # nosec B603 — список аргументов без оболочки
        [sys.executable, "-m", "pip_audit", *args, "--progress-spinner", "off"]
        + ["--cache-dir", str(ROOT / ".venv" / "pip-audit-cache")]
        + ["--format", "json", "--output", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode not in (0, 1) or not path.exists():
        raise SystemExit(f"pip-audit не выполнился:\n{result.stderr.strip()}")
    data = json.loads(path.read_text(encoding="utf-8"))
    found = []
    for dep in data["dependencies"]:
        if "skip_reason" in dep:
            found.append(f"{dep['name']}: пакет не проверен ({dep['skip_reason']})")
            continue
        for vuln in dep["vulns"]:
            fix = ", ".join(vuln.get("fix_versions", [])) or "нет"
            found.append(f"{dep['name']} {dep['version']}: {vuln['id']}, исправлено в {fix}")
    # одна уязвимость может прийти из нескольких баз под разными псевдонимами
    if result.returncode and not found:
        raise SystemExit(f"pip-audit завершился с ошибкой:\n{result.stderr.strip()}")
    return list(dict.fromkeys(found))


def main():
    REPORTS.mkdir(exist_ok=True)
    failed = False
    for title, (report, args) in AUDITS.items():
        found = audit(report, args)
        if found:
            failed = True
            print(f"Уязвимости — {title}:")
            for line in found:
                print(f"  {line}")
        else:
            print(f"Известных уязвимостей нет — {title}")
    if failed:
        print("\nОбновите пакеты до версий с исправлениями и запустите make verify")
        sys.exit(1)


if __name__ == "__main__":
    main()
