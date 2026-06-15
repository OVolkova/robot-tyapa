set dotenv-load

default:
    @just --list

install:
    uv sync --extra dev

test:
    uv run pytest -v --cov --cov-report=term-missing --ignore=tests/test_integration.py

test-integration:
    uv run pytest tests/test_integration.py -v -s

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
