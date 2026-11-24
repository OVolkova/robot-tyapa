set positional-arguments

services := "hearing speech brain body"

default:
    @just --list

# run a command in protocol/ and in every service: just each uv run ruff check .
each +cmd:
    cd protocol && {{cmd}}
    for s in {{services}}; do (cd "services/$s" && {{cmd}}) || exit 1; done

# create / refresh every environment
sync:
    just each uv sync --extra dev

# run one service in the foreground (stop it in systemd first)
run svc:
    cd "services/{{svc}}" && uv run $([ -f .env ] && echo "--env-file .env") python -m "tyapa_{{svc}}"

# poke services: just cli ping | just cli say "hello" | just cli act sit | just cli fake-voice
cli *args:
    cd protocol && uv run python -m tyapa_protocol.cli "$@"

test:
    just each uv run --extra dev pytest -q

lint:
    just each uv run ruff check .

format:
    just each uv run ruff check --fix .
    just each uv run ruff format .

check: lint
    just each uv run ruff format --check .

ci: check test

status:
    systemctl --no-pager status 'tyapa*'

restart svc="":
    if [ -z "{{svc}}" ]; then sudo systemctl restart tyapa.target; else sudo systemctl restart "tyapa@{{svc}}"; fi

stop:
    sudo systemctl stop tyapa.target

logs svc="":
    journalctl -f -u "tyapa*{{svc}}*"
