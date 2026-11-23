"""Проверка правил проекта (часть make verify).

Ловит то, что запрещено CONTRIBUTING.md: пропущенные тесты, сниженные пороги,
отключённые правила анализаторов, исключения без обоснования и запуск контейнерного
окружения в обход make container-check.
"""

import re
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CHECKED_DIRS = ["app", "tests", "migrations", "tools"]
MIN_COVERAGE = 95
REQUIRED_RUFF_RULES = {"E", "W", "F", "B", "UP"}
REQUIRED_VERIFY_STEPS = ["rules", "tests-guard", "quality", "sast", "secrets", "test"]
DIND = "bash .github/ci/dind.sh"
DIND_CHECKS = {
    f'{DIND} exec make rules tests-guard quality TESTS_BASE="$TESTS_BASE"',
    f"{DIND} exec make sast secrets deps",
    f"{DIND} exec make test",
    f"{DIND} exec make migrations-check",
    f"{DIND} exec make backup-check",
    f"{DIND} exec make container-check",
}

SKIPPED_TEST = re.compile(
    r"pytest\.mark\.(skip|skipif|xfail)\b|pytest\.(skip|xfail|importorskip)\(|unittest\.skip"
)
SUPPRESSION = re.compile(r"#\s*(noqa|nosec)\b(.*)")
FORBIDDEN_COMMENT = re.compile(r"#\s*(type:\s*ignore|pragma:\s*no\s*cover)")
# код правила и причина через длинное тире: «noqa: E402 — после подмены настроек»
JUSTIFIED = re.compile(r"^:?\s*[A-Z]+\d+(\s*,\s*[A-Z]+\d+)*\s+—\s+\S")


def check_sources(errors):
    for folder in CHECKED_DIRS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            if path.name == Path(__file__).name:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, 1):
                place = f"{path.relative_to(ROOT)}:{number}"
                if SKIPPED_TEST.search(line):
                    errors.append(f"{place}: тесты нельзя пропускать (skip/xfail)")
                if FORBIDDEN_COMMENT.search(line):
                    errors.append(f"{place}: запрещённое исключение из проверки")
                match = SUPPRESSION.search(line)
                if match and not JUSTIFIED.match(match.group(2)):
                    errors.append(
                        f"{place}: исключение {match.group(1)} без кода правила и причины "
                        "(нужно: «код — причина»)"
                    )


def check_settings(errors):
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tool = config.get("tool", {})

    fail_under = tool.get("coverage", {}).get("report", {}).get("fail_under", 0)
    if fail_under < MIN_COVERAGE:
        errors.append(f"pyproject.toml: порог покрытия {fail_under} ниже {MIN_COVERAGE}")

    lint = tool.get("ruff", {}).get("lint", {})
    missing = REQUIRED_RUFF_RULES - set(lint.get("select", []))
    if missing:
        errors.append(f"pyproject.toml: из ruff убраны правила {sorted(missing)}")
    for key in ("ignore", "extend-ignore", "per-file-ignores"):
        if lint.get(key):
            errors.append(f"pyproject.toml: в ruff отключены правила ({key})")

    if tool.get("bandit", {}).get("skips"):
        errors.append("pyproject.toml: в bandit отключены проверки (skips)")

    pytest = tool.get("pytest", {}).get("ini_options", {})
    if pytest.get("testpaths") != ["tests"] or set(pytest.get("addopts", [])) & {
        "--no-cov",
        "--collect-only",
        "--co",
    }:
        errors.append("pyproject.toml: изменён запуск тестов или отключено покрытие")
    coverage = tool.get("coverage", {}).get("run", {})
    if coverage.get("source") != ["app"] or not coverage.get("branch") or coverage.get("omit"):
        errors.append("pyproject.toml: ослаблена проверка покрытия приложения")

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    verify = re.search(r"^verify:(.*)$", makefile, re.MULTILINE)
    steps = verify.group(1).split() if verify else []
    for step in REQUIRED_VERIFY_STEPS:
        if step not in steps:
            errors.append(f"Makefile: из make verify убран шаг {step}")

    # контейнерное окружение меняется только после успешной проверки
    up = re.search(r"^up:(.*)$", makefile, re.MULTILINE)
    if not up or "container-check" not in up.group(1).split():
        errors.append("Makefile: make up должен сначала выполнять make container-check")

    scan = re.search(r"^image-scan:(.*)$", makefile, re.MULTILINE)
    if not scan or "image" not in scan.group(1).split():
        errors.append("Makefile: перед сканированием образ должен собираться из текущего коммита")


def mandatory_commands(job: dict) -> set[str]:
    return {
        line.strip()
        for step in job.get("steps", [])
        if "if" not in step and step.get("continue-on-error", False) is False
        for line in step.get("run", "").splitlines()
    }


def check_workflow(errors):
    workflow = ROOT / ".github/workflows/ci.yml"
    if not workflow.is_file():
        errors.append("Отсутствует .github/workflows/ci.yml")
        return
    jobs = yaml.safe_load(workflow.read_text(encoding="utf-8")).get("jobs", {})
    checks = jobs.get("checks", {})
    build = jobs.get("build", {})
    for name, job in (("checks", checks), ("build", build)):
        if "if" in job or job.get("continue-on-error", False) is not False:
            errors.append(f"ci.yml: обязательное задание {name} ослаблено")
        if f"{DIND} start" not in mandatory_commands(job):
            errors.append(f"ci.yml: задание {name} должно поднимать DinD")
    missing = DIND_CHECKS - mandatory_commands(checks)
    errors.extend(f"ci.yml: отсутствует обязательная команда «{cmd}»" for cmd in sorted(missing))
    build_commands = mandatory_commands(build)
    for command in (f'{DIND} exec make image-scan IMAGE_TAG="$tag"', f'{DIND} registry "$TAG"'):
        if command not in build_commands:
            errors.append(f"ci.yml: отсутствует обязательная команда «{command}»")
    publish = jobs.get("publish", {})
    if build.get("needs") != "checks" or set(publish.get("needs", [])) != {"checks", "build"}:
        errors.append("ci.yml: сборка и публикация должны ждать обязательные проверки")
    if publish.get("if") != "github.event_name == 'push'":
        errors.append("ci.yml: публикация разрешена только для push с успешными проверками")


def main():
    errors = []
    check_sources(errors)
    check_settings(errors)
    check_workflow(errors)
    if errors:
        print("Нарушены правила проекта:")
        for error in errors:
            print("  " + error)
        sys.exit(1)
    print("Правила проекта соблюдены")


if __name__ == "__main__":
    main()
