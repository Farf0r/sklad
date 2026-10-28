#!/bin/bash
# Проверка требований к серверу (запускать на любом из двух серверов):
#   sudo bash deploy/scripts/check.sh
set -uo pipefail

failed=0
ok() { echo "  OK    $1"; }
fail() {
    echo "  FAIL  $1"
    failed=1
}
check() {
    local title=$1
    shift
    if "$@" >/dev/null 2>&1; then ok "$title"; else fail "$title"; fi
}

if [[ $EUID -ne 0 ]]; then
    echo "Запустите через sudo" >&2
    exit 1
fi

if [[ -f /etc/systemd/system/sklad.service ]]; then
    role=app
    allowed_ports="22 8000"
elif [[ -d /etc/postgresql ]]; then
    role=db
    allowed_ports="22 5432"
else
    echo "Не похоже ни на сервер приложения, ни на сервер БД" >&2
    exit 1
fi
echo "Сервер: $(hostname), роль: $role"

echo "== SSH"
sshd_conf=$(sshd -T)
check "root не входит по SSH" grep -qx "permitrootlogin no" <<<"$sshd_conf"
check "вход по паролю выключен" grep -qx "passwordauthentication no" <<<"$sshd_conf"

echo "== Firewall"
check "ufw включён" grep -q "Status: active" <<<"$(ufw status)"

echo "== Порты, открытые не только для localhost (разрешены: $allowed_ports)"
while read -r address; do
    port=${address##*:}
    case $address in
        127.* | \[::1\]*) continue ;;
    esac
    if [[ " $allowed_ports " == *" $port "* ]]; then
        ok "порт $port ($address)"
    else
        fail "лишний порт $port ($address)"
    fi
done < <(ss -tlnH | awk '{print $4}' | sort -u)

if [[ $role == app ]]; then
    echo "== Служба sklad"
    check "запускается при загрузке" systemctl is-enabled sklad
    check "работает" systemctl is-active sklad
    pid=$(systemctl show -p MainPID --value sklad)
    user=$(ps -o user= -p "$pid" 2>/dev/null | tr -d ' ')
    if [[ $user == sklad ]]; then ok "процесс $pid работает от пользователя sklad"; else fail "процесс работает от '$user'"; fi
    check "автоперезапуск после сбоя (Restart=on-failure)" \
        grep -qx "Restart=on-failure" <<<"$(systemctl show -p Restart sklad)"
    check "/health отвечает ok" grep -q '"status":"ok"' <<<"$(curl -s http://127.0.0.1:8000/health)"

    echo "== Файлы и права"
    perms=$(stat -c "%a %U %G" /etc/sklad/sklad.env)
    if [[ $perms == "640 root sklad" ]]; then ok "/etc/sklad/sklad.env: $perms"; else fail "/etc/sklad/sklad.env: $perms, нужно 640 root sklad"; fi
    if runuser -u sklad -- test -w /opt/sklad/app; then fail "sklad может менять код"; else ok "sklad не может менять код в /opt/sklad"; fi
    if git -C /opt/sklad ls-files | grep -qE '(^|/)\.env$'; then fail "в репозитории есть .env"; else ok "в репозитории нет .env с паролями"; fi
fi

if [[ $role == db ]]; then
    echo "== PostgreSQL"
    check "запускается при загрузке" systemctl is-enabled postgresql
    check "работает" systemctl is-active postgresql
    check "порт 5432 в firewall открыт только для сервера приложения" \
        grep -qE "^5432/tcp +ALLOW +192\.168\.56\.10( |$)" <<<"$(ufw status)"
    echo "  правила входа по сети в pg_hba.conf (кроме localhost):"
    grep -hE '^\s*host' /etc/postgresql/*/main/pg_hba.conf | grep -vE '127\.0\.0\.1/32|::1/128' | sed 's/^/    /'
fi

echo
if [[ $failed -eq 0 ]]; then echo "Все проверки пройдены"; else echo "Есть ошибки (FAIL)"; fi
exit $failed
