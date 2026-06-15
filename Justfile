set dotenv-load

default:
    @just --list

install:
    uv sync --extra dev

test:
    uv run pytest tests/unit -v --cov --cov-report=term-missing

test-integration:
    uv run pytest tests/integration -v -s

lint:
    uv run ruff check robot_tyapa/
    uv run ruff check tests/

format:
    uv run ruff check --fix robot_tyapa/
    uv run ruff format robot_tyapa/
    uv run ruff check --fix tests/
    uv run ruff format tests/

check: lint
    uv run ruff format --check robot_tyapa/

ci: check test
