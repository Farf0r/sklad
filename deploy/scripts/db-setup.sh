#!/bin/bash
# Сервер БД: PostgreSQL, база и пользователь sklad с минимальными правами,
# подключение к базе разрешено только с сервера приложения.
# Запуск после base-setup.sh: sudo bash deploy/scripts/db-setup.sh
set -euo pipefail

APP_IP=${APP_IP:-192.168.56.10}
DB_IP=${DB_IP:-192.168.56.11}
DB_NAME=sklad
DB_USER=sklad

if [[ $EUID -ne 0 ]]; then
    echo "Запустите через sudo" >&2
    exit 1
fi

read -rsp "Придумайте пароль пользователя $DB_USER в PostgreSQL: " password
echo
if [[ ! $password =~ ^[A-Za-z0-9]{12,}$ ]]; then
    echo "Пароль: только латинские буквы и цифры, не короче 12 символов" >&2
    exit 1
fi

echo "== PostgreSQL"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q postgresql
version=$(pg_lsclusters --no-header | awk '{print $1}' | sort -V | tail -n 1)
conf=/etc/postgresql/$version/main

echo "== Слушать только localhost и адрес во внутренней сети"
echo "listen_addresses = 'localhost,$DB_IP'" > "$conf/conf.d/sklad.conf"

# запускать PostgreSQL только после того, как поднят адрес внутренней сети
mkdir -p /etc/systemd/system/postgresql@.service.d
cat > /etc/systemd/system/postgresql@.service.d/network.conf <<EOF
[Unit]
After=network-online.target
Wants=network-online.target
EOF

echo "== Доступ: пользователь $DB_USER, база $DB_NAME, только с $APP_IP, только по паролю"
rule="host $DB_NAME $DB_USER $APP_IP/32 scram-sha-256"
grep -qxF "$rule" "$conf/pg_hba.conf" || echo "$rule" >> "$conf/pg_hba.conf"

systemctl daemon-reload
systemctl enable postgresql
systemctl restart postgresql

echo "== База $DB_NAME и пользователь $DB_USER"
cd /
# пароль передаётся через окружение, а не аргументом: так его не видно в списке процессов
DB_PASSWORD=$password runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 \
    -v db="$DB_NAME" -v user="$DB_USER" <<'SQL'
\getenv password DB_PASSWORD
SELECT format('CREATE ROLE %I', :'user')
    WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'user') \gexec
ALTER ROLE :"user" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    CONNECTION LIMIT 20 PASSWORD :'password';
SELECT format('CREATE DATABASE %I', :'db')
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db') \gexec
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"user";
\connect :db
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO :"user";
SQL

echo "== Firewall: порт 5432 только для сервера приложения"
ufw allow from "$APP_IP" to any port 5432 proto tcp comment "postgresql for sklad-app"
ufw status verbose

echo "== Готово, PostgreSQL слушает:"
ss -tln | grep ':5432'
