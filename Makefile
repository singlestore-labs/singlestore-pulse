# Python tooling for singlestore-pulse. Requires uv on PATH.

.PHONY: lint-check lint-fix format-check format-fix test test-cov install install-dev build clean check release

lint-check: ## Ruff lint check
	uv run ruff check src/

lint-fix: ## Ruff lint fix
	uv run ruff check --fix src/

format-check: ## Ruff format check
	uv run ruff format --check src/

format-fix: ## Ruff format
	uv run ruff format src/

test: ## Run tests
	uv run --group test pytest tests/ -v

test-cov: ## Run tests with coverage
	uv run --group test pytest tests/ --cov --cov-report=term-missing

install: ## Install package
	uv sync

install-dev: ## Install with all groups
	uv sync --all-groups

build: clean ## Build distributions
	uv build

clean: ## Clean artifacts
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

check: format-check lint-check test ## Pre-commit gate

release: ## Release (interactive, or VERSION=X.Y.Z for non-interactive)
	@uv run python scripts/python-release.py src/pulse_otel/version.py $(if $(VERSION),--version $(VERSION))
