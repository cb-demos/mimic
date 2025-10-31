#!/usr/bin/env python3
"""Generate version.json file with git commit information.

This script can be run manually or automatically via git hooks.
To set up automatic generation on every commit, run: make install-git-hooks
"""
import json
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def get_git_commit():
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit = result.stdout.strip()
        short_commit = commit[:7]
        return commit, short_commit
    except subprocess.CalledProcessError:
        return None, None


def main():
    """Generate version.json file."""
    # Get project root
    project_root = Path(__file__).parent.parent

    # Read version from pyproject.toml
    pyproject = project_root / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
        version = data["project"]["version"]

    # Get git commit
    commit, short_commit = get_git_commit()

    # Generate version data
    version_data = {
        "version": version,
        "commit": commit,
        "commit_short": short_commit,
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Write to src/mimic/version.json
    output_path = project_root / "src" / "mimic" / "version.json"
    with open(output_path, "w") as f:
        json.dump(version_data, f, indent=2)

    print(f"Generated {output_path}")
    print(f"  Version: {version}")
    print(f"  Commit: {short_commit} ({commit})")


if __name__ == "__main__":
    main()
