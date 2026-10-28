#!/bin/bash
# Обновление (или откат) приложения на сервере до тега или ветки.
# app-setup.sh устанавливает этот скрипт как /usr/local/sbin/sklad-update:
#   sudo sklad-update v0.2.0
set -euo pipefail

ref=${1:?Укажите тег или ветку, например: v0.2.0}
APP_DIR=/opt/sklad

if [[ $EUID -ne 0 ]]; then
    echo "Запустите через sudo" >&2
    exit 1
fi

cd "$APP_DIR"
git fetch --tags --prune origin
if git rev-parse -q --verify "origin/$ref" >/dev/null; then
    target=origin/$ref
else
    target=$ref
fi
git checkout -q --detach "$target"
echo "== Версия кода: $(git describe --tags --always)"

.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m compileall -q app migrations
chown -R root:root "$APP_DIR"
chmod -R u=rwX,go=rX "$APP_DIR"

# в версиях до 0.2.0 файлов развёртывания ещё нет, тогда остаются установленные
if [[ -d deploy ]]; then
    install -m 644 deploy/sklad.service /etc/systemd/system/sklad.service
    install -m 755 deploy/scripts/sklad-cli.sh /usr/local/sbin/sklad-cli
    install -m 755 deploy/scripts/app-update.sh /usr/local/sbin/sklad-update
    systemctl daemon-reload
fi

# резервное копирование появилось в версии 0.3.0
if [[ -f app/backup.py ]]; then
    command -v pg_dump >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -q postgresql-client
    install -d -m 750 -o sklad -g sklad /var/backups/sklad
    grep -q '^BACKUP_DIR=' /etc/sklad/sklad.env || echo "BACKUP_DIR=/var/backups/sklad" >> /etc/sklad/sklad.env
    echo "== Резервная копия базы перед обновлением"
    /usr/local/sbin/sklad-cli backup
fi

# миграции появились в версии 0.3.0; при откате на более старую версию схема не меняется
if [[ -f alembic.ini ]]; then
    echo "== Миграции базы данных"
    /usr/local/sbin/sklad-cli migrate
fi
systemctl restart sklad

echo "== Проверка: ждём ответа приложения"
for _ in $(seq 1 20); do
    if health=$(curl -fs http://127.0.0.1:8000/health); then
        echo "$health"
        exit 0
    fi
    sleep 1
done
echo "После обновления приложение не отвечает 20 секунд. Последние строки журнала службы:" >&2
journalctl -u sklad -n 15 --no-pager >&2
exit 1
