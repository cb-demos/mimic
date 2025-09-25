import hashlib
import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.auth import get_auth_service
from src.cleanup import get_cleanup_service
from src.config import settings
from src.database import get_database, initialize_database
from src.exceptions import PipelineError, UnifyAPIError, ValidationError
from src.scenario_service import ScenarioService
from src.scenarios import initialize_scenarios
from src.scheduler import get_scheduler, start_scheduler, stop_scheduler
from src.security import NoValidPATFoundError, validate_encryption_key
from src.unify import UnifyAPIClient

logger = logging.getLogger(__name__)


def handle_auth_errors(func: Callable) -> Callable:
    """Decorator to handle common authentication and API errors consistently."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTPExceptions without modification
            raise
        except NoValidPATFoundError as e:
            # Extract email from request args
            email = getattr(kwargs.get("request"), "email", "unknown")
            if hasattr(args[0] if args else None, "email"):
                email = args[0].email

            logger.error(f"No valid PAT found for user {email}: {e}")
            raise HTTPException(
                status_code=401,
                detail=f"No valid CloudBees PAT found for {email}. Please update your credentials.",
            ) from e
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            raise HTTPException(status_code=400, detail=str(e)) from e
        except PipelineError as e:
            logger.error(f"Pipeline error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Pipeline execution failed at {e.step}: {str(e)}",
            ) from e
        except UnifyAPIError as e:
            logger.error(f"UnifyAPI error: {e}")
            raise HTTPException(
                status_code=400, detail=f"CloudBees API error: {str(e)}"
            ) from e
        except ValueError as e:
            logger.error(f"Value error: {e}")
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail="Operation failed") from e

    return wrapper


# Dictionary to hold asset hashes for cache busting
asset_hashes = {}


def compute_asset_hashes():
    """Compute SHA256 hashes for files in the static directory."""
    static_dir = "static"
    for filename in os.listdir(static_dir):
        filepath = os.path.join(static_dir, filename)
        if os.path.isfile(filepath):
            with open(filepath, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                asset_hashes[filename] = file_hash[:8]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    # Validate encryption key first
    if not validate_encryption_key():
        raise RuntimeError(
            "PAT_ENCRYPTION_KEY is invalid or missing. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    print("✓ Encryption key validated")

    # Initialize database first
    await initialize_database()
    print("✓ Database initialized")

    # Initialize scenario manager at startup
    initialize_scenarios("scenarios")
    print("✓ Scenario manager initialized")

    # Compute asset hashes for cache busting
    compute_asset_hashes()
    templates.env.globals["asset_hashes"] = asset_hashes
    print("✓ Asset hashes computed")

    # Start background cleanup scheduler
    await start_scheduler()
    print("✓ Cleanup scheduler started")

    yield
    # Cleanup on shutdown
    await stop_scheduler()
    print("✓ Cleanup scheduler stopped")
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="A simple internal FastAPI service",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class InstantiateRequest(BaseModel):
    organization_id: str
    email: str
    invitee_username: str | None = None
    parameters: dict[str, Any] | None = None
    expires_in_days: int | None = 7  # Default to 7 days, None for no expiration


class OrganizationRequest(BaseModel):
    organization_id: str
    email: str


class VerifyTokensRequest(BaseModel):
    email: str
    unify_pat: str
    github_pat: str | None = None
    name: str | None = None


class AuthStatusResponse(BaseModel):
    authenticated: bool
    email: str | None = None
    name: str | None = None
    has_github_pat: bool = False


class LogoutRequest(BaseModel):
    email: str


class SessionResponse(BaseModel):
    id: str
    scenario_id: str
    created_at: str
    expires_at: str | None
    parameters: dict[str, Any] | None
    resource_count: int


class ResourceResponse(BaseModel):
    id: str
    resource_type: str
    resource_name: str
    platform: str
    status: str
    created_at: str


class CleanupResponse(BaseModel):
    success: bool
    session_id: str
    total_resources: int
    successful: int
    failed: int
    errors: list[str]
    session_deleted: bool


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main UI page showing all scenarios."""
    service = ScenarioService()
    scenarios_data = service.list_scenarios()

    # Process scenarios for the UI
    scenarios = []
    for scenario_data in scenarios_data:
        scenario = service.get_scenario(scenario_data["id"])
        if scenario:
            scenario_info = {
                "id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
                "repositories": len(scenario.repositories),
                "applications": len(scenario.applications),
                "environments": len(scenario.environments),
                "parameters": {},
                "wip": scenario.wip,
            }

            # Add parameter schema if available
            if scenario.parameter_schema:
                for prop_name, prop in scenario.parameter_schema.properties.items():
                    scenario_info["parameters"][prop_name] = {
                        "type": prop.type,
                        "description": prop.description,
                        "placeholder": prop.placeholder,
                        "pattern": prop.pattern,
                        "enum": prop.enum,
                        "required": prop_name in scenario.parameter_schema.required,
                    }

            scenarios.append(scenario_info)

    # Sort scenarios: non-WIP first, then by name
    scenarios.sort(key=lambda x: (x["wip"], x["name"]))

    return templates.TemplateResponse(request, "index.html", {"scenarios": scenarios})


@app.get("/ui", response_class=HTMLResponse)
async def ui_redirect(request: Request):
    """Redirect /ui to main page."""
    return await root(request)


@app.get("/api", include_in_schema=False)
async def api_root():
    """API-only root endpoint."""
    return {"message": "Welcome to Mimic API"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy", service=settings.APP_NAME, version=settings.VERSION
    )


@app.get("/scenarios")
async def list_scenarios():
    """List all available scenarios with their parameter schemas."""
    service = ScenarioService()
    return service.list_scenarios()


@app.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get details for a specific scenario."""
    service = ScenarioService()
    scenario = service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{scenario_id}' not found"
        )

    # Return scenario details with schema
    result = {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description,
        "repositories": len(scenario.repositories),
    }

    if scenario.parameter_schema:
        schema_dict = {}
        for prop_name, prop in scenario.parameter_schema.properties.items():
            schema_dict[prop_name] = {
                "type": prop.type,
                "description": prop.description,
                "placeholder": prop.placeholder,
                "pattern": prop.pattern,
                "enum": prop.enum,
                "required": prop_name in scenario.parameter_schema.required,
            }
        result["parameters"] = schema_dict

    return result


@app.post("/api/organizations/details")
@handle_auth_errors
async def get_organization_details(request: OrganizationRequest):
    """
    Get organization details from CloudBees Platform API.

    This endpoint fetches organization information using the user's stored PAT
    and returns the display name.
    """
    auth_service = get_auth_service()

    # Get user's CloudBees PAT from database
    unify_pat = await auth_service.get_pat(request.email, "cloudbees")

    with UnifyAPIClient(api_key=unify_pat) as client:
        org_data = client.get_organization(request.organization_id)

        # Extract what we need from the known response structure
        org = org_data["organization"]
        return {"id": org["id"], "displayName": org["displayName"]}


@app.post("/api/auth/verify-tokens", response_model=AuthStatusResponse)
async def verify_tokens(request: VerifyTokensRequest):
    """
    Verify and store user authentication tokens.

    This endpoint:
    1. Validates the provided email format
    2. Stores encrypted tokens in the database
    3. Returns user authentication status
    """
    try:
        # Validate CloudBees email domain
        if not request.email or not request.email.strip().lower().endswith(
            "@cloudbees.com"
        ):
            raise HTTPException(
                status_code=400, detail="Only CloudBees email addresses are allowed"
            )

        auth_service = get_auth_service()

        # Store user tokens (auth service handles encryption)
        user_details = await auth_service.store_user_tokens(
            email=request.email,
            unify_pat=request.unify_pat,
            github_pat=request.github_pat,
            name=request.name,
        )

        # Update user activity
        await auth_service.refresh_user_activity(request.email)

        return AuthStatusResponse(
            authenticated=True,
            email=user_details["email"],
            name=user_details.get("name"),
            has_github_pat=user_details["has_github_pat"],
        )

    except ValueError as e:
        logger.error(f"Validation error in auth: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error in auth: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed") from e


@app.get("/api/auth/status", response_model=AuthStatusResponse)
async def get_auth_status(email: str):
    """Check if a user is authenticated by verifying they have stored tokens."""
    try:
        # Add email validation - must be CloudBees email
        if not email or not email.strip().lower().endswith("@cloudbees.com"):
            return AuthStatusResponse(authenticated=False)

        email = email.lower().strip()
        auth_service = get_auth_service()

        # Try to get a working PAT - this will raise NoValidPATFoundError if none exists
        await auth_service.get_pat(email, "cloudbees")

        # Check if user has GitHub PAT
        has_github_pat = True
        try:
            await auth_service.get_pat(email, "github")
        except NoValidPATFoundError:
            has_github_pat = False

        # Update activity if authenticated
        await auth_service.refresh_user_activity(email)

        return AuthStatusResponse(
            authenticated=True, email=email, has_github_pat=has_github_pat
        )

    except NoValidPATFoundError:
        # User not authenticated - this is expected behavior
        return AuthStatusResponse(authenticated=False)
    except Exception as e:
        logger.error(f"Unexpected error in auth status check for {email}: {e}")
        return AuthStatusResponse(authenticated=False)


@app.post("/api/auth/logout")
async def logout(request: LogoutRequest):
    """Clear user authentication (placeholder - tokens remain in DB for now)."""
    try:
        # For now, this just returns success
        # In a full implementation, we might mark tokens as inactive
        # or implement session-based auth with session invalidation
        return {"success": True, "message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Error in logout: {e}")
        raise HTTPException(status_code=500, detail="Logout failed") from e


@app.post("/instantiate/{scenario_id}")
@handle_auth_errors
async def instantiate_scenario(scenario_id: str, request: InstantiateRequest):
    """
    Execute a complete scenario using the Creation Pipeline.

    This will:
    1. Create repositories from templates with content replacements
    2. Create CloudBees components for repos that need them
    3. Create feature flags
    4. Create environments
    5. Create applications linking components and environments
    6. Configure flags across environments
    """
    service = ScenarioService()
    auth_service = get_auth_service()

    # Get user's CloudBees PAT from database
    unify_pat = await auth_service.get_pat(request.email, "cloudbees")

    result = await service.execute_scenario(
        scenario_id=scenario_id,
        organization_id=request.organization_id,
        unify_pat=unify_pat,
        email=request.email,
        invitee_username=request.invitee_username,
        parameters=request.parameters,
        expires_in_days=request.expires_in_days,
    )
    return result


@app.get("/api/my/sessions", response_model=list[SessionResponse])
@handle_auth_errors
async def list_my_sessions(request: Request):
    """
    List all sessions for the authenticated user with resource counts.

    Headers:
        X-User-Email: User's email address for session lookup

    Returns:
        List of user sessions with metadata
    """
    # Get email from header
    email = request.headers.get("X-User-Email")
    if not email:
        raise HTTPException(status_code=400, detail="X-User-Email header is required")

    # Validate CloudBees email domain
    if not email.strip().lower().endswith("@cloudbees.com"):
        raise HTTPException(
            status_code=400, detail="Only CloudBees email addresses are allowed"
        )

    email = email.lower().strip()

    # Verify user is authenticated by checking for valid PAT
    auth_service = get_auth_service()
    await auth_service.get_pat(email, "cloudbees")  # This will raise if no valid PAT

    # Get user sessions
    db = get_database()
    sessions = await db.get_user_sessions(email)

    # Convert to response models
    session_responses = []
    for session in sessions:
        import json

        parameters = None
        if session["parameters"]:
            try:
                parameters = json.loads(session["parameters"])
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse parameters for session {session['id']}: {e}"
                )
                parameters = {}  # Use empty dict as fallback

        session_responses.append(
            SessionResponse(
                id=session["id"],
                scenario_id=session["scenario_id"],
                created_at=session["created_at"],
                expires_at=session["expires_at"],
                parameters=parameters,
                resource_count=session["resource_count"],
            )
        )

    return session_responses


@app.get("/api/sessions/{session_id}/resources", response_model=list[ResourceResponse])
@handle_auth_errors
async def list_session_resources(session_id: str, request: Request):
    """
    List all resources in a specific session.

    Args:
        session_id: The session ID to get resources for

    Headers:
        X-User-Email: User's email address for ownership verification

    Returns:
        List of resources in the session
    """
    # Get email from header
    email = request.headers.get("X-User-Email")
    if not email:
        raise HTTPException(status_code=400, detail="X-User-Email header is required")

    # Validate CloudBees email domain
    if not email.strip().lower().endswith("@cloudbees.com"):
        raise HTTPException(
            status_code=400, detail="Only CloudBees email addresses are allowed"
        )

    email = email.lower().strip()

    # Verify user is authenticated
    auth_service = get_auth_service()
    await auth_service.get_pat(email, "cloudbees")

    # Verify session ownership
    db = get_database()
    session = await db.fetchone(
        "SELECT * FROM resource_sessions WHERE id = ? AND email = ?",
        (session_id, email),
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or not owned by {email}",
        )

    # Get session resources
    resources = await db.get_session_resources(session_id)

    # Convert to response models
    resource_responses = []
    for resource in resources:
        resource_responses.append(
            ResourceResponse(
                id=resource["id"],
                resource_type=resource["resource_type"],
                resource_name=resource["resource_name"],
                platform=resource["platform"],
                status=resource["status"],
                created_at=resource["created_at"],
            )
        )

    return resource_responses


@app.delete("/api/sessions/{session_id}", response_model=CleanupResponse)
@handle_auth_errors
async def cleanup_session(session_id: str, request: Request):
    """
    Clean up all resources in a specific session.

    Args:
        session_id: The session ID to clean up

    Headers:
        X-User-Email: User's email address for ownership verification

    Returns:
        Cleanup operation results
    """
    # Get email from header
    email = request.headers.get("X-User-Email")
    if not email:
        raise HTTPException(status_code=400, detail="X-User-Email header is required")

    # Validate CloudBees email domain
    if not email.strip().lower().endswith("@cloudbees.com"):
        raise HTTPException(
            status_code=400, detail="Only CloudBees email addresses are allowed"
        )

    email = email.lower().strip()

    # Verify user is authenticated
    auth_service = get_auth_service()
    await auth_service.get_pat(email, "cloudbees")

    # Execute cleanup
    cleanup_service = get_cleanup_service()
    try:
        result = await cleanup_service.cleanup_session(session_id, email)

        return CleanupResponse(
            success=result["failed"] == 0,
            session_id=result["session_id"],
            total_resources=result["total_resources"],
            successful=result["successful"],
            failed=result["failed"],
            errors=result["errors"],
            session_deleted=result["session_deleted"],
        )

    except ValueError as e:
        # Session not found or not owned by user
        raise HTTPException(status_code=404, detail=str(e)) from e


# Admin endpoints for cleanup monitoring and management
@app.get("/api/cleanup/status")
@handle_auth_errors
async def get_cleanup_status(request: Request):
    """
    Get the current status of the cleanup scheduler.

    Note: This is an admin endpoint that requires valid user authentication.
    Future versions may implement role-based access control.

    Headers:
        X-User-Email: User's email address for authentication

    Returns information about the scheduler state, last run, and next run time.
    """
    # Basic authentication - require valid user email
    email = request.headers.get("X-User-Email")
    if not email:
        raise HTTPException(
            status_code=400,
            detail="X-User-Email header is required for admin endpoints",
        )

    # Verify user exists in system (basic authentication check)
    auth_service = get_auth_service()
    try:
        # This will throw an exception if the user doesn't exist or has invalid PATs
        await auth_service.get_pat(email, "cloudbees")
    except Exception as e:
        raise HTTPException(
            status_code=401, detail="Invalid user authentication"
        ) from e

    scheduler = get_scheduler()
    return scheduler.get_job_status()


@app.post("/api/cleanup/trigger")
@handle_auth_errors
async def trigger_cleanup(request: Request):
    """
    Manually trigger a cleanup job.

    Note: This is an admin endpoint that requires valid user authentication.
    Future versions may implement role-based access control.

    Headers:
        X-User-Email: User's email address for authentication

    This will run the two-stage cleanup process immediately.
    """
    # Basic authentication - require valid user email
    email = request.headers.get("X-User-Email")
    if not email:
        raise HTTPException(
            status_code=400,
            detail="X-User-Email header is required for admin endpoints",
        )

    # Verify user exists in system (basic authentication check)
    auth_service = get_auth_service()
    try:
        # This will throw an exception if the user doesn't exist or has invalid PATs
        await auth_service.get_pat(email, "cloudbees")
    except Exception as e:
        raise HTTPException(
            status_code=401, detail="Invalid user authentication"
        ) from e

    scheduler = get_scheduler()
    return await scheduler.trigger_cleanup_now()
