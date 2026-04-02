# Load .env if it exists (never committed — local credentials only)
-include .env
export

.PHONY: test test-unit test-integration lint format analyze-local install

install:
	pip install -e ".[dev]"

test: test-unit test-integration

test-unit:
	python -m pytest tests/ -v --ignore=tests/test_integration.py

test-integration:
	python -m pytest tests/test_integration.py -v

lint:
	python -m ruff check cifi/ tests/
	python -m ruff format --check cifi/ tests/

format:
	python -m ruff format cifi/ tests/
	python -m ruff check --fix cifi/ tests/

analyze-local:
	@echo "Usage: python -m cifi <logfile> [workspace]"
	@echo "Example: python -m cifi /tmp/ci-log.txt ."

action-build:
	docker build -t cifi-action -f action/Dockerfile .

action-test: action-build
	docker run --rm cifi-action python -c "import cifi; print('cifi import OK')"
