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
.venv/bin/python -m compileall -q app
chown -R root:root "$APP_DIR"
chmod -R u=rwX,go=rX "$APP_DIR"

# в версиях до 0.2.0 файлов развёртывания ещё нет, тогда остаются установленные
if [[ -d deploy ]]; then
    install -m 644 deploy/sklad.service /etc/systemd/system/sklad.service
    install -m 755 deploy/scripts/sklad-cli.sh /usr/local/sbin/sklad-cli
    systemctl daemon-reload
fi
systemctl restart sklad

for _ in $(seq 1 20); do
    if curl -fsS http://127.0.0.1:8000/health; then
        echo
        exit 0
    fi
    sleep 1
done
echo "После обновления приложение не отвечает: journalctl -u sklad -n 50" >&2
exit 1
