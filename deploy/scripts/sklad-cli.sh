#!/bin/bash
# Команды приложения (python -m app.cli) от имени пользователя sklad и с настройками сервера.
# Устанавливается как /usr/local/sbin/sklad-cli. Пример:
#   sudo sklad-cli create-user --username admin --role admin
set -euo pipefail

cd /opt/sklad
exec runuser -u sklad -- bash -c \
    'set -a; . /etc/sklad/sklad.env; set +a; exec .venv/bin/python -m app.cli "$@"' sklad-cli "$@"
