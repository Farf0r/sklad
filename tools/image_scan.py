"""Анализ образа приложения (make image-scan, этап CI «Сборка образа»).

Сканер Trivy запускается из официального образа aquasec/trivy, закреплённого версией и
digest, и проверяет собранный образ: пакеты Debian и пакеты Python. Проверка не проходит,
если найдена уязвимость уровня HIGH или CRITICAL, для которой уже вышло исправление: нужно
обновить пакет или базовый образ (docs/docker.md, раздел 10). Полный отчёт со всеми
уровнями — reports/trivy.json.

База уязвимостей Trivy хранится в томе Docker sklad-trivy-cache и обновляется, когда устареет.
Скрипт использует только стандартную библиотеку Python: виртуальное окружение ему не нужно.
"""

import json
import subprocess  # nosec B404 — запуск сканера в контейнере
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "trivy.json"
TRIVY_IMAGE = (
    "aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c"
)
BLOCKING = ("HIGH", "CRITICAL")


def scan(image: str) -> dict:
    # сокет Docker нужен Trivy, чтобы прочитать образ с этого компьютера
    command = ["docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock"]
    command += ["-v", "sklad-trivy-cache:/root/.cache", TRIVY_IMAGE]
    command += [
        "image",
        "--quiet",
        "--scanners",
        "vuln",
        "--image-src",
        "docker",
        "--format",
        "json",
        image,
    ]
    result = subprocess.run(  # nosec B603 — список аргументов без оболочки
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    if result.returncode != 0:
        sys.exit(f"Trivy завершился с ошибкой:\n{result.stderr.strip()}")
    report = json.loads(result.stdout)
    REPORT.write_text(result.stdout, encoding="utf-8")
    if not report.get("Results"):
        sys.exit("Trivy не вернул результаты анализа образа (reports/trivy.json)")
    return report


def vulnerabilities(report: dict) -> list[dict]:
    return [v for r in report.get("Results", []) for v in r.get("Vulnerabilities") or []]


def blocking(vulns: list[dict]) -> list[dict]:
    """Уязвимости, которые запрещают публикацию: HIGH или CRITICAL, и есть исправление."""
    return [v for v in vulns if v.get("Severity") in BLOCKING and v.get("FixedVersion")]


def main():
    image = sys.argv[1]
    vulns = vulnerabilities(scan(image))
    counts = Counter(v.get("Severity", "UNKNOWN") for v in vulns)
    summary = ", ".join(f"{level} {counts[level]}" for level in sorted(counts)) or "нет"
    print(f"Образ {image}: найдено уязвимостей — {summary}. Отчёт: reports/trivy.json")
    found = blocking(vulns)
    if found:
        print(f"\nУязвимости HIGH и CRITICAL, для которых есть исправление ({len(found)}):")
        for v in found:
            print(
                f"  {v['PkgName']} {v.get('InstalledVersion', '')}: {v['VulnerabilityID']} "
                f"{v['Severity']}, исправлено в {v['FixedVersion']}"
            )
        print("\nОбновите пакет или базовый образ (docs/docker.md, раздел 10)")
        sys.exit(1)
    print("Уязвимостей HIGH и CRITICAL с исправлением нет")


if __name__ == "__main__":
    main()
