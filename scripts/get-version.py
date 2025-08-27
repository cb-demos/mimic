#!/usr/bin/env python3
"""Get version from pyproject.toml for use in build scripts."""
import tomllib
from pathlib import Path

pyproject = Path(__file__).parent.parent / "pyproject.toml"
with open(pyproject, "rb") as f:
    data = tomllib.load(f)
    print(data["project"]["version"])