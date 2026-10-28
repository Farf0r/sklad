#!/bin/bash
# Общая настройка обоих серверов: обновления, вход по SSH только по ключам, firewall.
# Запуск от администратора: sudo bash deploy/scripts/base-setup.sh
set -euo pipefail

ADMIN_NET=${ADMIN_NET:-192.168.56.0/24}
APP_IP=${APP_IP:-192.168.56.10}
DB_IP=${DB_IP:-192.168.56.11}

if [[ $EUID -ne 0 || -z ${SUDO_USER:-} ]]; then
    echo "Запустите от имени администратора через sudo" >&2
    exit 1
fi

admin=$SUDO_USER
ssh_dir=$(getent passwd "$admin" | cut -d: -f6)/.ssh

# если ключа нет, после отключения паролей на сервер будет не зайти
if [[ ! -s $ssh_dir/authorized_keys ]]; then
    echo "Нет ключа в $ssh_dir/authorized_keys. Сначала скопируйте открытый ключ с ноутбука" >&2
    exit 1
fi

echo "== Пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q ufw curl git netcat-openbsd

echo "== SSH: вход только по ключу, root не входит"
cat > /etc/ssh/sshd_config.d/10-sklad.conf <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers $admin
EOF
chmod 644 /etc/ssh/sshd_config.d/10-sklad.conf
chown -R "$admin:" "$ssh_dir"
chmod 700 "$ssh_dir"
chmod 600 "$ssh_dir/authorized_keys"
sshd -t
systemctl reload ssh

echo "== Имена серверов"
grep -q "^$APP_IP " /etc/hosts || echo "$APP_IP sklad-app" >> /etc/hosts
grep -q "^$DB_IP " /etc/hosts || echo "$DB_IP sklad-db" >> /etc/hosts

echo "== Firewall: входящие запрещены, кроме SSH из внутренней сети"
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$ADMIN_NET" to any port 22 proto tcp comment "ssh"
ufw --force enable
ufw status verbose
