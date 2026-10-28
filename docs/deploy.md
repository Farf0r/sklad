# Развёртывание на Linux-серверах

Приложение работает на двух виртуальных машинах с Debian 13 без графического интерфейса и без контейнеров: на одной — приложение как systemd-служба, на другой — PostgreSQL. Все шаги, кроме установки самой ОС, выполняются скриптами из каталога `deploy/`, поэтому развёртывание можно повторить на чистых машинах.

## 1. Схема

```
 Ноутбук (Windows, VirtualBox)          внутренняя сеть 192.168.56.0/24 (адаптер Host-only)
 браузер, ssh: 192.168.56.1
        │
        │ 8000 (веб), 22 (ssh)
        ▼
 ┌──────────────────────┐   5432    ┌──────────────────────┐
 │ sklad-app            │ ────────▶ │ sklad-db             │
 │ 192.168.56.10        │           │ 192.168.56.11        │
 │ служба sklad         │           │ PostgreSQL 17        │
 └──────────────────────┘           └──────────────────────┘
```

У каждой машины два сетевых адаптера: **NAT** — выход в интернет (пакеты, pip, git), **Host-only** — внутренняя сеть с постоянными адресами. Снаружи к машинам можно подключиться только через внутреннюю сеть.

| Машина | Адрес | Назначение | Ресурсы | Входящие подключения |
|---|---|---|---|---|
| `sklad-app` | 192.168.56.10 | приложение | 1 CPU, 1 ГБ RAM, диск 10 ГБ | 22 и 8000 из 192.168.56.0/24 |
| `sklad-db` | 192.168.56.11 | PostgreSQL | 1 CPU, 1 ГБ RAM, диск 10 ГБ | 22 из 192.168.56.0/24, 5432 только с 192.168.56.10 |

## 2. Подготовка машин

Выполняется для обеих машин, отличаются только имя и адрес.

### 2.1. Машина в VirtualBox

1. **Файл → Инструменты → Network Manager → Host-only Networks**: должен быть адаптер с адресом `192.168.56.1/24`. Если его нет — **Create**.
2. **Создать**:
   - имя `sklad-app` (`sklad-db`), образ `debian-13.x.x-amd64-netinst.iso`;
   - **отметить «Skip Unattended Installation»**, иначе VirtualBox сам поставит систему с рабочим столом;
   - память 1024 МБ, 1 процессор, диск 10 ГБ.
3. **Настроить → Сеть**:
   - Адаптер 1 — **NAT**;
   - Адаптер 2 — включить, **Виртуальный адаптер хоста** (Host-only), сеть из п. 1.

### 2.2. Установка Debian

Пункт меню **Install** (не Graphical install). Важные ответы:

| Вопрос установщика | Ответ |
|---|---|
| Language / Keyboard | English / American English (сообщения об ошибках проще искать) |
| Location | other → Europe → Russian Federation, затем locale `en_US.UTF-8` — так часовой пояс будет московским |
| Primary network interface | `enp0s3` — это NAT, через него ставятся пакеты |
| Hostname | `sklad-app` или `sklad-db`, домен пустой |
| Root password | **оставить пустым**: вход под root будет заблокирован, а созданный пользователь получит `sudo` |
| Username | `sysadmin` — администратор сервера |
| Partitioning | Guided — use entire disk → All files in one partition |
| Software selection | **снять** Debian desktop environment и GNOME, **оставить** SSH server и standard system utilities |
| GRUB | Yes, `/dev/sda` |

### 2.3. Постоянный адрес во внутренней сети

В окне машины войти как `sysadmin`. Второй адаптер (`enp0s8`) установщик не настраивает:

```bash
ip -br a                              # enp0s8 без адреса
sudo nano /etc/network/interfaces
```

Добавить в конец (для `sklad-db` адрес `192.168.56.11`):

```
auto enp0s8
iface enp0s8 inet static
    address 192.168.56.10/24
```

Шлюз не указывается: в интернет машина ходит через NAT. Применить и проверить:

```bash
sudo ifup enp0s8
ip -br a                              # enp0s8 UP 192.168.56.10/24
ping -c 2 192.168.56.1                # ноутбук отвечает
```

### 2.4. Вход по SSH-ключу

На ноутбуке в PowerShell, один раз (на вопросы о файле и пароле к ключу можно нажимать Enter):

```powershell
ssh-keygen -t ed25519
```

Скопировать открытый ключ на каждую машину (последний раз вводится пароль `sysadmin`):

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh sysadmin@192.168.56.10 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh sysadmin@192.168.56.11 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Чтобы подключаться по имени (`ssh sklad-app`), в файл `%USERPROFILE%\.ssh\config` на ноутбуке:

```
Host sklad-app
    HostName 192.168.56.10
    User sysadmin

Host sklad-db
    HostName 192.168.56.11
    User sysadmin
```

### 2.5. Общая настройка: base-setup.sh

Скрипт ставит обновления и нужные пакеты, оставляет вход по SSH только по ключу и только для `sysadmin`, запрещает вход под root, включает firewall (входящие запрещены, кроме SSH из внутренней сети) и прописывает имена `sklad-app` и `sklad-db` в `/etc/hosts`. Если ключа в `~/.ssh/authorized_keys` нет, скрипт останавливается, чтобы не закрыть доступ к серверу.

На `sklad-app` репозиторий сразу клонируется туда, откуда будет работать приложение:

```bash
sudo apt update && sudo apt install -y git
sudo git clone https://github.com/Farf0r/sklad.git /opt/sklad
sudo bash /opt/sklad/deploy/scripts/base-setup.sh
```

На `sklad-db` — в домашний каталог, нужны только скрипты:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Farf0r/sklad.git ~/sklad
sudo bash ~/sklad/deploy/scripts/base-setup.sh
```

Проверка с ноутбука:

```powershell
ssh sklad-app                                            # входит без пароля
ssh -o PubkeyAuthentication=no sysadmin@192.168.56.10    # Permission denied (publickey)
ssh root@192.168.56.10                                   # Permission denied
```

| Пользователь / файл | Владелец, права | Зачем |
|---|---|---|
| `root` | без пароля, вход по SSH запрещён | администрирование только через `sudo`, действия видны в журнале |
| `sysadmin` | группа `sudo`, вход только по ключу | администратор сервера |
| `~sysadmin/.ssh` | `sysadmin`, 700 | иначе sshd не примет ключ |
| `~sysadmin/.ssh/authorized_keys` | `sysadmin`, 600 | открытые ключи, с которыми можно войти |
| `/etc/ssh/sshd_config.d/10-sklad.conf` | `root`, 644 | наши настройки SSH, основной файл не трогаем |

## 3. Сервер БД

На `sklad-db`:

```bash
sudo bash ~/sklad/deploy/scripts/db-setup.sh
```

Скрипт спросит пароль для пользователя БД `sklad` (латиница и цифры, не короче 12 символов). Пароль нигде не сохраняется, его нужно будет ввести ещё раз при настройке сервера приложения.

Что делает скрипт:

1. Ставит PostgreSQL (в Debian 13 — версия 17).
2. В `/etc/postgresql/17/main/conf.d/sklad.conf` задаёт `listen_addresses = 'localhost,192.168.56.11'`: PostgreSQL слушает только себя и внутреннюю сеть.
3. Добавляет в `pg_hba.conf` одно правило: `host sklad sklad 192.168.56.10/32 scram-sha-256` — пользователь `sklad`, только к базе `sklad`, только с сервера приложения, только по паролю. Остальные подключения по сети отклоняются.
4. Создаёт пользователя и базу с минимальными правами (см. таблицу ниже).
5. Открывает в firewall порт 5432 только для `192.168.56.10`.
6. Добавляет `After=network-online.target` для PostgreSQL, чтобы после перезагрузки он запускался, когда адрес внутренней сети уже поднят.

Повторный запуск безопасен: уже созданные пользователь, база и правила не дублируются, пароль меняется на новый.

| Кто / что | Права | Почему |
|---|---|---|
| пользователь БД `sklad` | вход по паролю; не суперпользователь, не может создавать базы, роли и реплицировать; не больше 20 подключений | приложению больше не нужно |
| база `sklad` | `CONNECT` только у `sklad`, у остальных (`PUBLIC`) отозвано | другие пользователи не подключатся к базе |
| схема `public` в базе `sklad` | `USAGE, CREATE` только у `sklad` | приложение при запуске создаёт свои таблицы; после перехода на миграции (ЛР3) права на `CREATE` можно будет убрать у пользователя приложения |
| системный пользователь `postgres` | создан пакетом, без пароля и входа по SSH | администрирование СУБД: `sudo -u postgres psql` |
| `/var/lib/postgresql/17/main` | `postgres`, 700 | файлы БД доступны только СУБД |

Проверка на `sklad-db`:

```bash
sudo ss -tlnp | grep 5432                      # 127.0.0.1:5432 и 192.168.56.11:5432
sudo ufw status                                # 5432/tcp ALLOW 192.168.56.10
sudo -u postgres psql -c '\du sklad'           # 20 connections, без лишних атрибутов
sudo -u postgres psql -c '\l sklad'            # права на базу: sklad=c
```

**База недоступна с постороннего узла.** Защита в три слоя: firewall пропускает 5432 только с `192.168.56.10`, `pg_hba.conf` разрешает вход только с этого адреса, PostgreSQL не слушает внешний адаптер NAT. Проверка с ноутбука (он для БД посторонний):

```powershell
Test-NetConnection 192.168.56.11 -Port 22      # TcpTestSucceeded : True  — машина доступна
Test-NetConnection 192.168.56.11 -Port 5432    # TcpTestSucceeded : False — порт БД закрыт
```

Ответ на второй команде приходит секунд через 20: firewall молча отбрасывает пакеты. С сервера приложения подключение есть:

```bash
nc -zv sklad-db 5432                           # succeeded
```

## 4. Требования к эксплуатации

| № | Требование | Как обеспечено | Как проверить |
|---|---|---|---|
| 1 | Приложение не запускается от root | служба работает от системного пользователя `sklad` без пароля и входа; `NoNewPrivileges`, пустой `CapabilityBoundingSet` | `ps -o user= -p $(systemctl show -p MainPID --value sklad)` |
| 2 | Лишние порты не открываются | firewall: входящие запрещены, разрешены только 22, 8000 (sklad-app) и 22, 5432 с 192.168.56.10 (sklad-db); PostgreSQL слушает только localhost и внутренний адрес | `sudo ss -tlnp`, `sudo ufw status` |
| 3 | Пароли не хранятся в репозитории | настройки сервера в `/etc/sklad/sklad.env` (только на сервере, права 640); в репозитории образец `deploy/sklad.env.example` с заглушками; пароль БД вводится при запуске скрипта, `SECRET_KEY` генерируется на сервере | `git ls-files`, `cat deploy/sklad.env.example` |
| 4 | Root не входит удалённо, вход только по ключам | `PermitRootLogin no`, `PasswordAuthentication no`, `AllowUsers sysadmin` | `sudo sshd -T \| grep -E 'permitroot\|passwordauth'` |
| 5 | Приложение не может менять свой код и систему | код в `/opt/sklad` принадлежит root; `ProtectSystem=strict` делает систему для службы доступной только на чтение | `sudo runuser -u sklad -- touch /opt/sklad/x` → Permission denied |
| 6 | Служба стартует при загрузке и после сбоя | `systemctl enable`, `Restart=on-failure` | `systemctl is-enabled sklad`, `systemctl show -p Restart sklad` |
| 7 | БД доступна только серверу приложения | firewall + `pg_hba.conf` + `listen_addresses` | раздел 3 |

Все требования проверяются одной командой на каждом сервере:

```bash
sudo bash /opt/sklad/deploy/scripts/check.sh      # на sklad-app
sudo bash ~/sklad/deploy/scripts/check.sh         # на sklad-db
```

Скрипт печатает `OK` или `FAIL` по каждому пункту и завершается с ошибкой, если хоть один пункт не выполнен.
