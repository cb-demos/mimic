from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.config import settings
from src.creation_pipeline import CreationPipeline
from src.scenarios import get_scenario_manager, initialize_scenarios


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    # Initialize scenario manager at startup
    initialize_scenarios("scenarios")
    print("✓ Scenario manager initialized")
    yield
    # Cleanup on shutdown if needed
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
    unify_pat: str
    invitee_username: str | None = None
    parameters: dict[str, Any] | None = None


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main UI page showing all scenarios."""
    manager = get_scenario_manager()
    scenarios_data = manager.list_scenarios()

    # Process scenarios for the UI
    scenarios = []
    for scenario_data in scenarios_data:
        scenario = manager.get_scenario(scenario_data["id"])
        if scenario:
            scenario_info = {
                "id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
                "repositories": len(scenario.repositories),
                "applications": len(scenario.applications),
                "environments": len(scenario.environments),
                "parameters": {},
            }

            # Add parameter schema if available
            if scenario.parameter_schema:
                for prop_name, prop in scenario.parameter_schema.properties.items():
                    scenario_info["parameters"][prop_name] = {
                        "type": prop.type,
                        "description": prop.description,
                        "pattern": prop.pattern,
                        "enum": prop.enum,
                        "required": prop_name in scenario.parameter_schema.required,
                    }

            scenarios.append(scenario_info)

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
    manager = get_scenario_manager()
    return manager.list_scenarios()


@app.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Get details for a specific scenario."""
    manager = get_scenario_manager()
    scenario = manager.get_scenario(scenario_id)
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
                "pattern": prop.pattern,
                "enum": prop.enum,
                "required": prop_name in scenario.parameter_schema.required,
            }
        result["parameters"] = schema_dict

    return result


@app.post("/instantiate/{scenario_id}")
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
    manager = get_scenario_manager()
    scenario = manager.get_scenario(scenario_id)

    if not scenario:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{scenario_id}' not found"
        )

    # Default empty dict if None
    parameters = request.parameters or {}

    try:
        # Validate input parameters
        scenario.validate_input(parameters)

        # Create and execute pipeline
        pipeline = CreationPipeline(
            organization_id=request.organization_id,
            endpoint_id=settings.CLOUDBEES_ENDPOINT_ID,
            invitee_username=request.invitee_username,
            unify_pat=request.unify_pat,
        )

        # Execute the complete scenario
        summary = await pipeline.execute_scenario(scenario, parameters)

        return {
            "status": "success",
            "message": "Scenario executed successfully",
            "scenario_id": scenario_id,
            "parameters": parameters,
            "organization_id": request.organization_id,
            "invitee_username": request.invitee_username,
            "summary": summary,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Pipeline execution failed: {str(e)}"
        ) from e
