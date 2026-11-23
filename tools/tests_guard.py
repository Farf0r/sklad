"""Проверяет, что относительно базового коммита не потеряны файлы и функции тестов."""

import argparse
import ast
import subprocess  # nosec B404 — чтение файлов из Git
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.check_output(  # nosec B603, B607 — Git без оболочки
        ["git", *args], cwd=ROOT, encoding="utf-8"
    )


def test_names(source: str) -> set[str]:
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    names = set()
    for node in ast.parse(source).body:
        if isinstance(node, functions) and node.name.startswith("test"):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            names.update(
                f"{node.name}.{method.name}"
                for method in node.body
                if isinstance(method, functions) and method.name.startswith("test")
            )
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="базовый коммит для сравнения")
    base = git(
        "rev-parse", "--verify", "--end-of-options", f"{parser.parse_args().base}^{{commit}}"
    )
    commit = base.strip()
    names = git("ls-tree", "-r", "--name-only", "-z", commit, "--", "tests/").split("\0")
    problems = []
    for name in filter(None, names):
        path = ROOT / name
        if not path.is_file():
            problems.append(f"удалён файл {name}")
        elif path.suffix == ".py" and path.name.startswith("test"):
            before = test_names(git("show", f"{commit}:{name}"))
            after = test_names(path.read_text(encoding="utf-8"))
            problems.extend(f"удалён тест {name}::{test}" for test in sorted(before - after))
    if problems:
        raise SystemExit("Проверка состава тестов не пройдена:\n  " + "\n  ".join(problems))
    print(f"Файлы и функции тестов из базового коммита {commit[:7]} сохранены")


if __name__ == "__main__":
    main()
