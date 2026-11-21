#!/usr/bin/env bash
# Develop against the real Pi without touching the production Mopidy:
# code is synced to /tmp on the Pi and run in throwaway containers built from
# the production `mopidy:latest` image, on the same Docker network as Invidious.
#
#   dev/remote.sh test     run unit tests
#   dev/remote.sh up       start isolated Mopidy (+ extension) as $NAME
#   dev/remote.sh e2e      sync, (re)start and run dev/e2e.py against it
#   dev/remote.sh logs     follow its logs
#   dev/remote.sh down     remove the container and synced files
set -euo pipefail

# Local overrides (HOST=user@docker-host, ...) go in the untracked dev/local.env
[ -f "$(dirname "$0")/local.env" ] && . "$(dirname "$0")/local.env"
HOST="${HOST:?set HOST=user@docker-host (env or dev/local.env)}"
IMAGE="${IMAGE:-mopidy:latest}"
NETWORK="${NETWORK:-nginx-proxy-manager_default}"
NAME="mopidy-invidious-dev"
REMOTE_DIR="/tmp/mopidy-invidious-dev"

cd "$(dirname "$0")/.."

sync() {
    tar --exclude=__pycache__ --exclude=.git --exclude=.venv -czf - \
        pyproject.toml README.md src tests dev |
        ssh "$HOST" "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR && tar -xzf - -C $REMOTE_DIR"
}

install_cmd="cp -r /src /tmp/w && pip install -q --user --break-system-packages --no-deps -e /tmp/w"

case "${1:-}" in
test)
    sync
    ssh "$HOST" "docker run --rm -v $REMOTE_DIR:/src:ro --entrypoint sh $IMAGE -c \
        '$install_cmd pytest pluggy iniconfig 2>/dev/null && cd /tmp/w && python3 -m pytest -q'"
    ;;
up)
    sync
    ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1; \
        docker run -d --name $NAME --network $NETWORK -v $REMOTE_DIR:/src:ro \
            --entrypoint sh $IMAGE -c '$install_cmd && exec mopidy --config /tmp/w/dev/mopidy.conf' >/dev/null && \
        for i in \$(seq 1 60); do sleep 2; docker exec $NAME curl -sf -o /dev/null http://localhost:6680/ && exit 0; done; \
        docker logs $NAME; exit 1"
    echo "$NAME is up"
    ;;
e2e)
    "$0" up
    ssh "$HOST" "docker exec $NAME python3 /tmp/w/dev/e2e.py"
    ;;
logs)
    ssh "$HOST" "docker logs -f $NAME"
    ;;
down)
    ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1; rm -rf $REMOTE_DIR"
    ;;
*)
    sed -n '2,12p' "$0"
    exit 1
    ;;
esac
