.PHONY: help dev run test lint typecheck format build clean install

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

dev: ## Run development server with auto-reload
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

run: ## Run production server
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

test: ## Run tests
	uv run pytest tests/ -v

lint: ## Run linting
	uv run ruff check src/ tests/

typecheck: ## Run type checking with pyright
	uv run pyright src/

format: ## Format code
	uv run ruff format src/ tests/

build: ## Build Docker image for multiple architectures
	@VERSION=$$(python scripts/get-version.py); \
	echo "Building mimic:$$VERSION for multiple architectures"; \
	docker buildx create --use --name multiarch-builder --driver docker-container --bootstrap 2>/dev/null || docker buildx use multiarch-builder; \
	docker buildx build --platform linux/amd64,linux/arm64 -t cloudbeesdemo/mimic:$$VERSION -t cloudbeesdemo/mimic:latest --push .

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .nox