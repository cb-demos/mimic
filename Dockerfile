# UI build stage
FROM node:20-alpine AS ui-builder

WORKDIR /app/web-ui

# Copy web-ui package files
COPY web-ui/package*.json ./

# Install dependencies
RUN npm install

# Copy web-ui source
COPY web-ui/ ./

# Build the UI (outputs to ../src/mimic/web/static)
RUN npm run build

# Python build stage
FROM python:3.13-slim AS python-builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Copy virtual environment from Python builder
COPY --from=python-builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY scenarios/ ./scenarios/

# Copy built UI from UI builder
COPY --from=ui-builder /app/src/mimic/web/static ./src/mimic/web/static

# Set Python path to use virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Set entrypoint to mimic CLI
ENTRYPOINT ["mimic"]

# Default to showing help
CMD ["--help"]