# Build stage
FROM python:3.13-slim AS builder

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

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ ./src/
COPY scenarios/ ./scenarios/
COPY static/ ./static/
COPY templates/ ./templates/

# Set Python path to use virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Set default mode to API
ENV MODE=api

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (only used in API mode)
EXPOSE 8000

# Health check (only applies to API mode)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD if [ "$MODE" = "api" ]; then python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"; else exit 0; fi

# Run the application based on mode
CMD ["sh", "-c", "if [ \"$MODE\" = \"mcp\" ]; then python -m src.mcp_main; else uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --forwarded-allow-ips='*' --proxy-headers; fi"]