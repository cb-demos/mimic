"""FastAPI server for Mimic web UI."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mimic.config_manager import ConfigManager
from mimic.exceptions import (
    CredentialError,
    GitHubError,
    KeyringUnavailableError,
    PipelineError,
    ScenarioError,
    UnifyAPIError,
    ValidationError,
)

from .api import cleanup, config, packs, scenarios, setup, tenants, version
from .error_handler import (
    handle_credential_error,
    handle_generic_exception,
    handle_github_error,
    handle_keyring_error,
    handle_pipeline_error,
    handle_scenario_error,
    handle_unify_error,
    handle_validation_error,
)
from .middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)

# Static files path
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown tasks."""
    # Startup: Ensure official scenario pack is configured
    try:
        config_manager = ConfigManager()
        was_added = config_manager.ensure_official_pack_exists()
        if was_added:
            logger.info("Official scenario pack automatically added to configuration")
    except Exception as e:
        logger.warning(f"Failed to ensure official pack exists: {e}")

    yield

    # Shutdown: cleanup tasks if needed
    pass


# Create FastAPI app
app = FastAPI(
    title="Mimic API",
    description="API for CloudBees demo scenario orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

# Add request context middleware (should be first for request tracking)
app.add_middleware(RequestContextMiddleware)

# Add CORS middleware for local development
# Allow localhost origins only for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Vite dev server default
        "http://localhost:5173",  # Vite dev server alt port
        "http://localhost:8080",  # Production build served by FastAPI
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers - Using centralized error handlers with proper typing
@app.exception_handler(ValidationError)
async def validation_error_handler_wrapper(request: Request, exc: Exception):
    """Handle validation errors from Mimic."""
    return await handle_validation_error(request, exc)  # type: ignore


@app.exception_handler(PipelineError)
async def pipeline_error_handler_wrapper(request: Request, exc: Exception):
    """Handle pipeline errors from Mimic."""
    return await handle_pipeline_error(request, exc)  # type: ignore


@app.exception_handler(GitHubError)
async def github_error_handler_wrapper(request: Request, exc: Exception):
    """Handle GitHub API errors."""
    return await handle_github_error(request, exc)  # type: ignore


@app.exception_handler(UnifyAPIError)
async def unify_error_handler_wrapper(request: Request, exc: Exception):
    """Handle CloudBees Unify API errors."""
    return await handle_unify_error(request, exc)  # type: ignore


@app.exception_handler(CredentialError)
async def credential_error_handler_wrapper(request: Request, exc: Exception):
    """Handle credential errors."""
    return await handle_credential_error(request, exc)  # type: ignore


@app.exception_handler(KeyringUnavailableError)
async def keyring_error_handler_wrapper(request: Request, exc: Exception):
    """Handle keyring unavailable errors."""
    return await handle_keyring_error(request, exc)  # type: ignore


@app.exception_handler(ScenarioError)
async def scenario_error_handler_wrapper(request: Request, exc: Exception):
    """Handle scenario loading/processing errors."""
    return await handle_scenario_error(request, exc)  # type: ignore


# Catch-all handler for unexpected exceptions
@app.exception_handler(Exception)
async def generic_exception_handler_wrapper(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    return await handle_generic_exception(request, exc)


# Keep HTTPException handler for FastAPI's own exceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions from FastAPI."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "mimic-api"}


# Register API routers
app.include_router(scenarios.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(tenants.router, prefix="/api")
app.include_router(cleanup.router, prefix="/api")
app.include_router(packs.router, prefix="/api")
app.include_router(setup.router, prefix="/api")
app.include_router(version.router, prefix="/api")


# Static file serving for production builds
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Mount static assets (JS, CSS, etc.) with caching
    app.mount(
        "/assets",
        StaticFiles(directory=str(STATIC_DIR / "assets")),
        name="static-assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """
        Serve the React SPA for all non-API routes.
        This enables client-side routing to work correctly.
        """
        # If the path points to a file that exists, serve it
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Otherwise, serve index.html for SPA routing
        return FileResponse(STATIC_DIR / "index.html")

else:
    logger.warning(
        f"Static files not found at {STATIC_DIR}. "
        "Run 'cd web-ui && npm run build' to build the UI."
    )

    @app.get("/")
    async def root():
        """Fallback when static files are not built."""
        return {
            "message": "Mimic API is running",
            "docs": "/docs",
            "note": "Web UI not built. Run 'cd web-ui && npm run build' to build it.",
        }
