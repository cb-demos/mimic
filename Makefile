.PHONY: help test lint typecheck format build build-ui dev-ui clean install

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync

generate-version: ## Generate version.json with git commit info
	python scripts/generate-version.py

test: ## Run tests
	uv run pytest tests/ -v

lint: ## Run linting
	uv run ruff check src/ tests/

typecheck: ## Run type checking with pyright
	uv run pyright src/

format: ## Format code
	uv run ruff format src/ tests/

build-ui: ## Build the web UI (React app)
	@echo "Building web UI..."
	cd web-ui && npm install && npm run build
	@echo "Web UI built to src/mimic/web/static/"

dev-ui: ## Run the web UI development server
	cd web-ui && npm run dev

build: build-ui ## Build and push Docker image with UI for multiple architectures
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
	rm -rf src/mimic/web/static
	rm -rf web-ui/node_modules
	rm -rf web-ui/dist