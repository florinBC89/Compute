.PHONY: help up down logs migrate bootstrap install test test-sdk test-api test-benchmark test-lookup-sql lint fmt benchmark clean

help:
	@echo "up         start postgres, redis and the api"
	@echo "down       stop everything"
	@echo "migrate    apply database migrations"
	@echo "bootstrap  create the local workspace, project and API key"
	@echo "install    install the SDK and API in editable mode"
	@echo "test       run the whole test suite"
	@echo "test-lookup-sql  check reuse SQL against a real database"
	@echo "benchmark  run the research-agent benchmark"

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

migrate:
	alembic upgrade head

bootstrap:
	cd apps/api && python -m app.bootstrap

install:
	pip install -e packages/python-sdk
	pip install -r apps/api/requirements-dev.txt

test: test-sdk test-benchmark test-api

test-sdk:
	cd packages/python-sdk && python -m pytest tests -q

test-api:
	cd apps/api && python -m pytest tests -q

test-benchmark:
	cd benchmarks/research-agent && python -m unittest -q

# Checks the reuse SQL against a real database: tied timestamps, partial-index
# predicates and constraint interactions that the Python suite cannot produce.
test-lookup-sql:
	createdb computelayer_lookup_check 2>/dev/null || true
	psql -d computelayer_lookup_check -v ON_ERROR_STOP=1 \
	     -f migrations/schema.sql -f apps/api/tests/lookup_semantics.sql
	dropdb computelayer_lookup_check

lint:
	ruff check packages/python-sdk/computelayer apps/api/app

fmt:
	ruff format packages/python-sdk apps/api

benchmark:
	python benchmarks/research-agent/run_benchmark.py --all

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
