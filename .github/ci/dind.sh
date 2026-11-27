#!/usr/bin/env bash
set -euo pipefail

dind="${CI_DIND_CONTAINER:-sklad-ci-dind}"
dind_image=docker:29.9.2-dind@sha256:9e79b879b177fbd72c34376a3dd3d91747da5db49e1f560f76aea59561471977
postgres_image=postgres:17.11-trixie@sha256:31ba9c94a03ada9988f2bb493a22a75eef3a185884533e5cdbcd498ea835b08f
registry_image=registry:3.1.2@sha256:82f6ff4a7f982960c8aa51617fea3aabc485df6e55cce80d22deb1de36f1bc3c

inner() {
    docker exec -w /workspace "$dind" docker "$@"
}

worker() {
    inner exec sklad-ci-worker "$@"
}

case "${1:-}" in
    start)
        # У внутреннего демона только Unix-сокет. Порты на хост не пробрасываются.
        docker run --detach --privileged --name "$dind" \
            --mount "type=bind,source=${CI_WORKSPACE:-$PWD},target=/workspace" \
            "$dind_image" dockerd --host=unix:///var/run/docker.sock
        for ((i=0; i<45; i++)); do
            if inner info >/dev/null 2>&1; then break; fi
            sleep 2
        done
        outer_id=$(docker info --format '{{.ID}}')
        inner_id=$(inner info --format '{{.ID}}')
        [[ -n "$inner_id" && "$outer_id" != "$inner_id" ]]
        echo "Docker runner: $outer_id"
        echo "Docker-in-Docker: $inner_id"
        inner build --tag sklad-ci-worker .github/ci
        # Пути исходников совпадают для Compose. Loopback относится к DinD.
        inner run --detach --name sklad-ci-worker --network host \
            --mount type=bind,source=/workspace,target=/workspace \
            --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
            sklad-ci-worker sleep infinity
        worker docker compose version
        worker pg_dump --version
        ;;
    database)
        password=$(openssl rand -hex 24)
        key=$(openssl rand -hex 32)
        admin_password=$(openssl rand -hex 24)
        app_password=$(openssl rand -hex 24)
        if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
            for value in "$password" "$key" "$admin_password" "$app_password"; do
                printf '::add-mask::%s\n' "$value"
            done
        fi
        umask 077
        url="postgresql+psycopg://sklad:${password}@127.0.0.1:5432/sklad_test"
        printf 'TEST_DATABASE_URL=%s\n' "$url" > .env.test
        printf 'APP_ENV=test\nDATABASE_URL=%s\nSECRET_KEY=%s\nPOSTGRES_PASSWORD=%s\nSKLAD_DB_PASSWORD=%s\n' \
            "$url" "$key" "$admin_password" "$app_password" > .env
        # Сам Docker читает пароль из переменной, а не из текста команды.
        docker exec -e POSTGRES_PASSWORD="$password" "$dind" docker run --detach \
            --name sklad-ci-postgres -p 127.0.0.1:5432:5432 \
            -e POSTGRES_USER=sklad -e POSTGRES_PASSWORD -e POSTGRES_DB=sklad_test \
            "$postgres_image"
        for ((i=0; i<45; i++)); do
            if worker pg_isready -h 127.0.0.1 -U sklad -d sklad_test; then exit 0; fi
            sleep 2
        done
        inner logs sklad-ci-postgres
        exit 1
        ;;
    registry)
        tag=${2:?нужен тег образа}
        local_image="127.0.0.1:5000/sklad:$tag"
        inner run --detach --name sklad-ci-registry -p 127.0.0.1:5000:5000 "$registry_image"
        worker python -c 'from urllib.request import urlopen; from time import sleep
for i in range(30):
    try:
        urlopen("http://127.0.0.1:5000/v2/", timeout=2).close()
        break
    except OSError:
        if i == 29:
            raise
        sleep(1)'
        original=$(inner image inspect "sklad:$tag" --format '{{.Id}}')
        inner tag "sklad:$tag" "$local_image"
        inner push "$local_image"
        inner image rm "$local_image"
        inner pull "$local_image"
        test "$(inner image inspect "$local_image" --format '{{.Id}}')" = "$original"
        echo "Образ из локального registry совпадает со сборкой: $original"
        ;;
    exec)
        shift
        worker "$@"
        ;;
    stop)
        docker rm --force --volumes "$dind"
        ;;
    *)
        echo "Использование: $0 {start|database|registry|exec|stop}" >&2
        exit 2
        ;;
esac
