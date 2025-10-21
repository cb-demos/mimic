"""FastAPI server for Mimic web UI."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mimic.exceptions import PipelineError, ValidationError

from .api import cleanup, config, environments, packs, scenarios, setup

logger = logging.getLogger(__name__)

# Static files path
STATIC_DIR = Path(__file__).parent / "static"

# Create FastAPI app
app = FastAPI(
    title="Mimic API",
    description="API for CloudBees demo scenario orchestration",
    version="1.0.0",
)

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


# Exception handlers
@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc: ValidationError):
    """Handle validation errors from Mimic."""
    return JSONResponse(
        status_code=400,
        content={"error": "Validation Error", "detail": str(exc)},
    )


@app.exception_handler(PipelineError)
async def pipeline_error_handler(request, exc: PipelineError):
    """Handle pipeline errors from Mimic."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Pipeline Error",
            "detail": str(exc),
            "step": exc.step,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions."""
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
app.include_router(environments.router, prefix="/api")
app.include_router(cleanup.router, prefix="/api")
app.include_router(packs.router, prefix="/api")
app.include_router(setup.router, prefix="/api")


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
