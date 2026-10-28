"""Резервная копия, намеренная порча данных и восстановление на тестовой базе."""

import os
import sys
from decimal import Decimal

import pytest
from sqlalchemy import text

from app import backup, cli
from app.backup import BackupError, create_backup, latest_backup, restore_backup
from app.config import settings
from app.database import engine


@pytest.fixture
def backup_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def stock_data(admin_client):
    """Материал с остатком 40 после проведённого поступления."""
    unit = admin_client.post("/api/units", json={"name": "Килограмм", "short_name": "кг"}).json()
    material = admin_client.post(
        "/api/materials", json={"name": "Цемент М500", "unit_id": unit["id"], "min_stock": "10"}
    ).json()
    supplier = admin_client.post(
        "/api/suppliers", json={"name": "ООО СтройБаза", "inn": "7701234567"}
    ).json()
    items = [{"material_id": material["id"], "quantity": "40", "price": "450"}]
    receipt = admin_client.post(
        "/api/receipts", json={"supplier_id": supplier["id"], "items": items}
    ).json()
    admin_client.post(f"/api/receipts/{receipt['id']}/post")
    return material["id"]


def damage_data():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM receipts"))
        conn.execute(text("UPDATE materials SET stock = 0, name = 'испорчено'"))


def run_cli(monkeypatch, *args, answer="yes"):
    monkeypatch.setattr(sys, "argv", ["python -m app.cli", *args])
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    cli.main()


def test_restore_after_damage(admin_client, stock_data, backup_folder):
    path = create_backup()
    assert path.parent == backup_folder
    assert path.stat().st_size > 0

    damage_data()
    assert admin_client.get("/api/receipts").json() == []

    restore_backup(path)

    material = admin_client.get(f"/api/materials/{stock_data}").json()
    assert material["name"] == "Цемент М500"
    assert Decimal(material["stock"]) == 40
    assert Decimal(material["min_stock"]) == 10
    receipts = admin_client.get("/api/receipts").json()
    assert [receipt["status"] for receipt in receipts] == ["posted"]


def test_restore_returns_dropped_table(admin_client, stock_data, backup_folder):
    path = create_backup()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE receipt_items"))
    restore_backup(path)
    assert len(admin_client.get("/api/receipts").json()[0]["items"]) == 1


def test_backup_names_do_not_overwrite(backup_folder):
    first = create_backup()
    second = create_backup()
    assert first != second
    assert latest_backup() == second


def test_latest_backup_skips_copies_made_before_restore(backup_folder):
    regular = create_backup()
    before_restore = create_backup(suffix=backup.BEFORE_RESTORE)
    os.utime(regular, (1, 1))
    assert before_restore.stat().st_mtime > regular.stat().st_mtime
    assert latest_backup() == regular


def test_no_backups(backup_folder):
    with pytest.raises(BackupError, match="нет резервных копий"):
        latest_backup()


def test_restore_missing_file(backup_folder):
    with pytest.raises(BackupError, match="не найден"):
        restore_backup(backup_folder / "nope.dump")


def test_restore_broken_file_keeps_data(admin_client, stock_data, backup_folder):
    broken = backup_folder / "broken.dump"
    broken.write_text("это не резервная копия")
    with pytest.raises(BackupError, match="pg_restore"):
        restore_backup(broken)
    assert admin_client.get(f"/api/materials/{stock_data}").json()["name"] == "Цемент М500"


def test_tool_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(backup.shutil, "which", lambda name: None)
    monkeypatch.setattr(backup, "WINDOWS_PG_BIN", str(tmp_path / "*" / "bin"))
    with pytest.raises(BackupError, match="Не найдена утилита pg_dump"):
        backup.find_tool("pg_dump")


def test_tool_found_in_windows_folder(monkeypatch, tmp_path):
    # под Windows pg_dump лежит в C:/Program Files/PostgreSQL/<версия>/bin
    for version in ("15", "16"):
        folder = tmp_path / version / "bin"
        folder.mkdir(parents=True)
        (folder / "pg_dump.exe").touch()
    monkeypatch.setattr(backup.shutil, "which", lambda name: None)
    monkeypatch.setattr(backup, "WINDOWS_PG_BIN", str(tmp_path / "*" / "bin"))
    assert backup.find_tool("pg_dump") == str(tmp_path / "16" / "bin" / "pg_dump.exe")


def test_password_is_not_in_command_line(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs["env"]))
        return backup.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    backup.run(["pg_dump"])
    command, env = calls[0]
    password = backup.make_url(settings.database_url).password
    assert env["PGPASSWORD"] == password
    assert password not in " ".join(command)


def test_backup_and_restore_commands(monkeypatch, capsys, admin_client, stock_data, backup_folder):
    run_cli(monkeypatch, "backup")
    assert "Резервная копия создана" in capsys.readouterr().out

    damage_data()
    run_cli(monkeypatch, "restore")
    out = capsys.readouterr().out
    assert "Текущее состояние сохранено" in out
    assert "База восстановлена" in out
    assert admin_client.get(f"/api/materials/{stock_data}").json()["name"] == "Цемент М500"
    # копия испорченного состояния тоже есть
    assert len(list(backup_folder.glob(f"*{backup.BEFORE_RESTORE}.dump"))) == 1


# восстановить можно только явным «yes», любой другой ответ отменяет
@pytest.mark.parametrize("answer", ["no", "", "y", "да"])
def test_restore_command_can_be_cancelled(
    monkeypatch, capsys, admin_client, stock_data, backup_folder, answer
):
    path = create_backup()
    damage_data()
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "restore", str(path), answer=answer)
    assert "отменено" in capsys.readouterr().out
    assert admin_client.get(f"/api/materials/{stock_data}").json()["name"] == "испорчено"


def test_restore_command_errors(monkeypatch, capsys, backup_folder):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "restore", "--yes")
    assert "нет резервных копий" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "restore", str(backup_folder / "nope.dump"), "--yes")
    assert "не найден" in capsys.readouterr().out


def test_backup_command_error(monkeypatch, capsys, backup_folder):
    monkeypatch.setattr(backup.shutil, "which", lambda name: None)
    monkeypatch.setattr(backup, "WINDOWS_PG_BIN", str(backup_folder / "*" / "bin"))
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "backup")
    assert "Не найдена утилита pg_dump" in capsys.readouterr().out
