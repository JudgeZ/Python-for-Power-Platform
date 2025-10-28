.PHONY: install dev test lint format type coverage build security bandit openapi-check openapi-validate
install: ; python -m pip install -U pip && pip install -e .
dev: ; pip install -e .[dev,auth] && pre-commit install
test: ; pytest -q
lint: ; ruff check . && black --check .
format: ; ruff check --fix . && black .
type: ; mypy
coverage: ; pytest --cov=pacx --cov-report=term-missing --cov-report=xml --cov-report=json --cov-fail-under=81
build: ; python -m build
security: ; pip-audit && $(MAKE) bandit

bandit: ; bandit -c bandit.yaml -r src

openapi-check: ; bash scripts/validate_openapi.sh

openapi-validate: ; python -m scripts.openapi_validate validate
