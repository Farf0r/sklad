#!/bin/bash
# Сервер приложения: пользователь sklad, код в /opt/sklad, настройки в /etc/sklad, systemd-служба.
# Запуск после base-setup.sh и настройки сервера БД:
#   sudo git clone https://github.com/Farf0r/sklad.git /opt/sklad
#   sudo bash /opt/sklad/deploy/scripts/app-setup.sh
set -euo pipefail

APP_DIR=/opt/sklad
CONF_DIR=/etc/sklad
ENV_FILE=$CONF_DIR/sklad.env
DB_IP=${DB_IP:-192.168.56.11}
CLIENT_NET=${CLIENT_NET:-192.168.56.0/24}

if [[ $EUID -ne 0 ]]; then
    echo "Запустите через sudo" >&2
    exit 1
fi
if [[ ! -d $APP_DIR/.git ]]; then
    echo "Сначала склонируйте репозиторий: sudo git clone https://github.com/Farf0r/sklad.git $APP_DIR" >&2
    exit 1
fi

echo "== Пакеты"
export DEBIAN_FRONTEND=noninteractive
# postgresql-client — утилиты pg_dump и pg_restore для резервного копирования
apt-get install -y -q python3 python3-venv postgresql-client

echo "== Пользователь sklad: без пароля и без входа в систему, только для запуска приложения"
id sklad &>/dev/null || useradd --system --user-group --no-create-home \
    --home-dir /nonexistent --shell /usr/sbin/nologin sklad

echo "== Код и зависимости (владелец root: приложение не может менять свой код)"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
"$APP_DIR/.venv/bin/python" -m compileall -q "$APP_DIR/app" "$APP_DIR/migrations"
chown -R root:root "$APP_DIR"
chmod -R u=rwX,go=rX "$APP_DIR"

echo "== Настройки в $ENV_FILE"
install -d -m 750 -o root -g sklad "$CONF_DIR"
if [[ ! -f $ENV_FILE ]]; then
    read -rsp "Пароль пользователя sklad в PostgreSQL (тот, что задавали на сервере БД): " password
    echo
    secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -e "s|:DB_PASSWORD@|:$password@|" \
        -e "s|@192.168.56.11:|@$DB_IP:|" \
        -e "s|^SECRET_KEY=.*|SECRET_KEY=$secret|" \
        "$APP_DIR/deploy/sklad.env.example" > "$ENV_FILE"
fi
# в файлах, созданных версией 0.2.0, этой строки ещё нет
grep -q '^BACKUP_DIR=' "$ENV_FILE" || echo "BACKUP_DIR=/var/backups/sklad" >> "$ENV_FILE"
chown root:sklad "$ENV_FILE"
chmod 640 "$ENV_FILE"

echo "== Каталог резервных копий /var/backups/sklad"
install -d -m 750 -o sklad -g sklad /var/backups/sklad

echo "== Служба sklad"
install -m 644 "$APP_DIR/deploy/sklad.service" /etc/systemd/system/sklad.service
install -m 755 "$APP_DIR/deploy/scripts/sklad-cli.sh" /usr/local/sbin/sklad-cli
install -m 755 "$APP_DIR/deploy/scripts/app-update.sh" /usr/local/sbin/sklad-update

echo "== Миграции базы данных"
/usr/local/sbin/sklad-cli migrate

systemctl daemon-reload
systemctl enable sklad
systemctl restart sklad

echo "== Firewall: веб-интерфейс доступен из внутренней сети"
ufw allow from "$CLIENT_NET" to any port 8000 proto tcp comment "sklad web"

echo "== Проверка: ждём ответа приложения"
for _ in $(seq 1 20); do
    if health=$(curl -fs http://127.0.0.1:8000/health); then
        echo "$health"
        echo "Готово. Создайте администратора: sudo sklad-cli create-user --username admin --role admin"
        exit 0
    fi
    sleep 1
done
echo "Приложение не отвечает 20 секунд. Последние строки журнала службы:" >&2
journalctl -u sklad -n 15 --no-pager >&2
exit 1
