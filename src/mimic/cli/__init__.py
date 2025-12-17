"""CLI package for Mimic - CloudBees Unify scenario orchestration tool.

This package contains the main CLI application and all command modules:
- main: Core commands (list, run, upgrade, setup, ui)
- env: Environment management commands
- config: Configuration commands
- cleanup: Resource cleanup commands
- scenario_pack: Scenario pack management commands
- display: Display helper functions
"""

from .main import app

__all__ = ["app"]
