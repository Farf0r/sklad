"""Проверка резервного копирования на тестовой базе (make backup-check, этап CI «Резервное
копирование»).

Используются те же команды, что make backup и make restore (python -m app.cli backup / restore):
1. в базе создаются данные;
2. делается резервная копия;
3. данные портятся: материал удаляется, название единицы меняется;
4. база восстанавливается из копии — данные вернулись, состояние до восстановления сохранено;
5. повреждённый файл копии отклоняется, и база остаётся как была.

Копии пишутся во временный каталог, в конце он удаляется вместе с данными тестовой базы.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from tools.check_helpers import CheckFailed, require, run_app, step, use_test_database


def main():
    use_test_database()
    # приложение импортируется только после подмены настроек
    from sqlalchemy import MetaData, text

    from app.database import engine

    def drop_everything():
        metadata = MetaData()
        metadata.reflect(bind=engine)
        metadata.drop_all(bind=engine)

    def marker():
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT m.stock, u.name FROM materials m JOIN units u ON u.id = m.unit_id "
                    "WHERE m.name = 'backup-check'"
                )
            ).one_or_none()

    folder = Path(tempfile.mkdtemp(prefix="sklad-backup-check-"))
    env = {"BACKUP_DIR": str(folder)}
    print(f"Проверка резервного копирования на базе {engine.url.database}\n")
    try:
        step("Подготовка: схема и данные")
        drop_everything()
        run_app("migrate")
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO units (name, short_name) VALUES ('Ящик', 'ящ')"))
            conn.execute(
                text(
                    "INSERT INTO materials (name, unit_id, stock) "
                    "SELECT 'backup-check', id, 7.5 FROM units WHERE short_name = 'ящ'"
                )
            )
        require(marker() is not None, "в базе есть материал backup-check, остаток 7.5 ящ")

        step("Резервная копия (python -m app.cli backup)")
        out = run_app("backup", **env)
        copies = list(folder.glob("*.dump"))
        require("Резервная копия создана" in out and len(copies) == 1, "создан файл копии")
        backup = copies[0]
        size = backup.stat().st_size
        require(size > 0, f"{backup.name}, {size} байт")

        step("Порча данных")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM materials WHERE name = 'backup-check'"))
            conn.execute(text("UPDATE units SET name = 'Испорчено' WHERE short_name = 'ящ'"))
        require(marker() is None, "материал удалён, название единицы изменено")

        step("Восстановление (python -m app.cli restore --yes)")
        out = run_app("restore", str(backup), "--yes", **env)
        require("База восстановлена" in out, "команда restore выполнена")
        row = marker()
        require(row is not None and row.stock == 7.5, "материал вернулся с прежним остатком")
        require(row.name == "Ящик", "название единицы восстановлено")
        saved = list(folder.glob("*before-restore*.dump"))
        require(len(saved) == 1, "состояние до восстановления сохранено в копию before-restore")

        step("Повреждённая копия не портит базу")
        broken = folder / "broken.dump"
        broken.write_bytes(b"not a backup")
        out = run_app("restore", str(broken), "--yes", check=False, **env)
        require("База восстановлена" not in out, "восстановление из повреждённого файла отклонено")
        require(marker() is not None, "данные в базе остались прежними")
    except CheckFailed as exc:
        print(f"\nПРОВЕРКА НЕ ПРОЙДЕНА: {exc}")
        sys.exit(1)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        drop_everything()
    print("\nРезервное копирование и восстановление работают")


if __name__ == "__main__":
    main()
