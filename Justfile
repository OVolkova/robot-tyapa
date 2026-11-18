set positional-arguments
set dotenv-load

services := "hearing speech brain body"

default:
    @just --list

# create / refresh every environment
sync:
    cd protocol && uv sync --extra dev
    for s in {{services}}; do (cd services/$s && uv sync --extra dev) || exit 1; done

# run one service in the foreground (stop it in systemd first)
run svc:
    cd services/{{svc}} && uv run $([ -f .env ] && echo "--env-file .env") python -m tyapa_{{svc}}

# poke services: just cli ping | just cli say "hello" | just cli act sit | just cli fake-voice
cli *args:
    cd protocol && uv run python -m tyapa_protocol.cli "$@"

test:
    cd protocol && uv run --extra dev pytest -q
    for s in {{services}}; do (cd services/$s && uv run --extra dev pytest -q) || exit 1; done

lint:
    cd protocol && uv run ruff check tyapa_protocol/ tests/
    for s in {{services}}; do (cd services/$s && uv run ruff check tyapa_$s/ tests/) || exit 1; done

format:
    cd protocol && uv run ruff check --fix tyapa_protocol/ tests/ && uv run ruff format tyapa_protocol/ tests/
    for s in {{services}}; do (cd services/$s && uv run ruff check --fix tyapa_$s/ tests/ && uv run ruff format tyapa_$s/ tests/) || exit 1; done

check: lint
    cd protocol && uv run ruff format --check tyapa_protocol/ tests/
    for s in {{services}}; do (cd services/$s && uv run ruff format --check tyapa_$s/ tests/) || exit 1; done

ci: check test

status:
    systemctl --no-pager status 'tyapa*'

restart svc="":
    if [ -z "{{svc}}" ]; then sudo systemctl restart tyapa.target; else sudo systemctl restart "tyapa@{{svc}}"; fi

stop:
    sudo systemctl stop tyapa.target

logs svc="":
    journalctl -f -u "tyapa*{{svc}}*"
