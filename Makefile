.PHONY: install lint format format-check typecheck test test-cov check pre-commit docker-build clean

install:
	uv sync --all-packages
	uv run pre-commit install

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=tg_summary_core --cov-report=term-missing --cov-report=xml

check: lint format-check typecheck test

pre-commit:
	uv run pre-commit run --all-files

docker-build:
	docker build -f apps/entrypoint/Dockerfile -t tg-group-summary:local .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache coverage.xml htmlcov .coverage
