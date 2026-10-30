"""Правила для Dockerfile, .dockerignore и Compose из make container-check (без запуска Docker)."""

import copy

import pytest

from tools.container_check import (
    ROOT,
    compose_problems,
    dockerfile_problems,
    dockerignore_problems,
    image_pinned,
)

DIGEST = "sha256:" + "a" * 64
DATA = "/var/lib/postgresql/data"
HEALTHCHECK = 'HEALTHCHECK --interval=10s \\\n    CMD ["python", "-c", "print(1)"]'

DOCKERFILE = f"""
ARG PYTHON_IMAGE=python:3.13.9-slim-trixie@{DIGEST}
FROM ${{PYTHON_IMAGE}} AS build
RUN pip install -r requirements.txt
FROM ${{PYTHON_IMAGE}}
ENV APP_ENV=prod
USER sklad
HEALTHCHECK --interval=10s \\
    CMD ["python", "-c", "print(1)"]
CMD ["uvicorn", "app.main:app"]
"""

COMPOSE = {
    "services": {
        "db": {
            "image": f"postgres:17.6-trixie@{DIGEST}",
            "healthcheck": {"test": ["CMD", "pg_isready"]},
            "volumes": [{"type": "volume", "source": "db-data", "target": DATA}],
            "deploy": {"resources": {"limits": {"cpus": 1, "memory": "536870912"}}},
        },
        "migrate": {
            "image": "sklad:1.0.0",
            "deploy": {"resources": {"limits": {"cpus": 0.5, "memory": "268435456"}}},
        },
        "app": {
            "image": "sklad:1.0.0",
            "build": {"context": "."},
            "ports": [{"host_ip": "127.0.0.1", "target": 8000, "published": "8080"}],
            "deploy": {"resources": {"limits": {"cpus": 0.5, "memory": "268435456"}}},
        },
    },
    "networks": {"backend": {"internal": True}, "frontend": {}},
}


@pytest.mark.parametrize(
    "ref, pinned",
    [
        (f"python:3.13.9-slim-trixie@{DIGEST}", True),
        (f"registry:5000/python:3.13@{DIGEST}", True),
        ("python:3.13.9-slim-trixie", False),
        (f"python:latest@{DIGEST}", False),
        (f"python@{DIGEST}", False),
        (f"registry:5000/python@{DIGEST}", False),
        ("python:3.13.X-slim-trixie@sha256:REPLACE-WITH-DIGEST", False),
        ("python:3.13.9-slim-trixie@sha256:abc", False),
    ],
)
def test_image_pinned(ref, pinned):
    assert image_pinned(ref) is pinned


def test_good_dockerfile_passes():
    assert dockerfile_problems(DOCKERFILE) == []


@pytest.mark.parametrize(
    "old, new, problem",
    [
        (f"@{DIGEST}", "", "не закреплён"),
        (f"3.13.9-slim-trixie@{DIGEST}", "latest", "не закреплён"),
        ("USER sklad", "", "нет USER"),
        ("USER sklad", "USER root", "нет USER"),
        ("USER sklad", "USER 0:0", "нет USER"),
        (HEALTHCHECK, "HEALTHCHECK NONE", "HEALTHCHECK"),
        ('CMD ["uvicorn", "app.main:app"]', "CMD uvicorn app.main:app", "exec-форме"),
        ("ENV APP_ENV=prod", "ENV DB_PASSWORD=qwerty", "секрет"),
        ("ENV APP_ENV=prod", "ARG SECRET_KEY=abc", "секрет"),
        ("ENV APP_ENV=prod", "ENV DATABASE_URL=postgresql://sklad:x@db/sklad", "секрет"),
    ],
)
def test_dockerfile_violations(old, new, problem):
    assert old in DOCKERFILE
    problems = dockerfile_problems(DOCKERFILE.replace(old, new))
    assert any(problem in p for p in problems), problems


def test_project_dockerignore_passes():
    assert dockerignore_problems((ROOT / ".dockerignore").read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "text",
    ["app/\nmigrations/\n", "*\n!app/\n!.env\n", "*\n!app/\n!backups/\n", "*\n!.git/\n"],
)
def test_dockerignore_violations(text):
    assert dockerignore_problems(text)


def test_good_compose_passes():
    assert compose_problems(COMPOSE, "1.0.0") == []


def broken(change):
    config = copy.deepcopy(COMPOSE)
    change(config["services"], config)
    return config


@pytest.mark.parametrize(
    "change, problem",
    [
        (lambda s, c: s["db"].update(image="postgres:latest"), "latest"),
        (lambda s, c: s["db"].update(image="postgres:17.6-trixie"), "не закреплён digest"),
        (lambda s, c: s["migrate"].update(image="sklad"), "без точного тега"),
        (lambda s, c: s["app"].update(user="root"), "от root"),
        (lambda s, c: s["db"].update(user="0:0"), "от root"),
        (lambda s, c: s["db"].update(healthcheck={"disable": True}), "healthcheck отключён"),
        (lambda s, c: s["app"].update(healthcheck={"test": ["NONE"]}), "healthcheck отключён"),
        (lambda s, c: s["db"].pop("healthcheck"), "db: нет healthcheck"),
        (lambda s, c: s["app"]["deploy"]["resources"]["limits"].pop("memory"), "ограничения"),
        (lambda s, c: s["migrate"].pop("deploy"), "ограничения"),
        (lambda s, c: s["db"].update(ports=[{"published": "5432"}]), "db: опубликован порт"),
        (lambda s, c: s["app"]["ports"][0].update(host_ip=""), "не только для 127.0.0.1"),
        (lambda s, c: s["db"].update(volumes=[]), "именованном томе"),
        (lambda s, c: s["db"]["volumes"][0].update(type="bind"), "именованном томе"),
        (lambda s, c: c["networks"]["backend"].pop("internal"), "internal"),
    ],
)
def test_compose_violations(change, problem):
    problems = compose_problems(broken(change), "1.0.0")
    assert any(problem in p for p in problems), problems


def test_app_image_tag_must_match_version():
    problems = compose_problems(COMPOSE, "1.1.0")
    assert any("не совпадает с версией 1.1.0" in p for p in problems)
