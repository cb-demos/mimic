#!/usr/bin/env python3
"""
CalVer version bumping script for Mimic.

Auto-increments version in pyproject.toml using CalVer format: YYYY.M.D.BUILD

Logic:
- If current version date == today: increment build number
- If current version date < today: use today's date with build 0
- Use --set X.Y.Z.B to manually override

Usage:
    python scripts/bump-version.py           # Auto-increment
    python scripts/bump-version.py --set 2025.11.6.1  # Manual override
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


def parse_calver(version: str) -> tuple[int, int, int, int]:
    """Parse CalVer string into (year, month, day, build)."""
    parts = version.split(".")
    if len(parts) != 4:
        raise ValueError(f"Invalid CalVer format: {version} (expected YYYY.M.D.BUILD)")

    try:
        year, month, day, build = (int(p) for p in parts)
        return (year, month, day, build)
    except ValueError as e:
        raise ValueError(f"Invalid CalVer format: {version} ({e})") from e


def format_calver(year: int, month: int, day: int, build: int) -> str:
    """Format CalVer tuple as string."""
    return f"{year}.{month}.{day}.{build}"


def get_today_calver() -> tuple[int, int, int]:
    """Get today's date as (year, month, day)."""
    now = datetime.now()
    return (now.year, now.month, now.day)


def increment_version(current_version: str) -> str:
    """
    Auto-increment version based on current date.

    - If version date == today: increment build
    - If version date < today: use today + build 0
    """
    year, month, day, build = parse_calver(current_version)
    today_year, today_month, today_day = get_today_calver()

    if (year, month, day) == (today_year, today_month, today_day):
        # Same day, increment build
        new_version = format_calver(year, month, day, build + 1)
        print(f"Same day: incrementing build number")
    elif (year, month, day) < (today_year, today_month, today_day):
        # New day, reset build to 0
        new_version = format_calver(today_year, today_month, today_day, 0)
        print(f"New day: resetting build number")
    else:
        # Version date is in the future (shouldn't happen)
        print(f"Warning: Current version date ({year}-{month:02d}-{day:02d}) is in the future!")
        print(f"Using today's date instead.")
        new_version = format_calver(today_year, today_month, today_day, 0)

    return new_version


def read_pyproject() -> tuple[str, str]:
    """Read pyproject.toml and extract current version."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    if not pyproject_path.exists():
        print(f"Error: pyproject.toml not found at {pyproject_path}")
        sys.exit(1)

    content = pyproject_path.read_text()

    # Find version line
    match = re.search(r'^version = ["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        print("Error: Could not find version field in pyproject.toml")
        sys.exit(1)

    current_version = match.group(1)
    return content, current_version


def write_pyproject(content: str, old_version: str, new_version: str) -> None:
    """Update version in pyproject.toml."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    # Replace version line
    new_content = re.sub(
        r'^version = ["\']' + re.escape(old_version) + r'["\']',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE
    )

    pyproject_path.write_text(new_content)
    print(f"Updated {pyproject_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Bump Mimic version using CalVer format (YYYY.M.D.BUILD)"
    )
    parser.add_argument(
        "--set",
        metavar="VERSION",
        help="Manually set version (e.g., --set 2025.11.6.1)"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )
    args = parser.parse_args()

    # Read current version
    content, current_version = read_pyproject()
    print(f"Current version: {current_version}")

    # Determine new version
    if args.set:
        # Manual override
        try:
            parse_calver(args.set)  # Validate format
            new_version = args.set
            print(f"Manually setting version")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # Auto-increment
        try:
            new_version = increment_version(current_version)
        except ValueError as e:
            print(f"Error: {e}")
            print(f"Hint: Current version must be in CalVer format (YYYY.M.D.BUILD)")
            sys.exit(1)

    print(f"New version: {new_version}")

    # Check if version is unchanged
    if new_version == current_version:
        print(f"Error: New version {new_version} is the same as current version")
        sys.exit(1)

    # Confirm
    if not args.yes:
        response = input(f"\nUpdate version from {current_version} to {new_version}? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Write updated version
    write_pyproject(content, current_version, new_version)
    print("\n✓ Version bumped successfully!")
    print(f"\nNext steps:")
    print(f"  git add pyproject.toml")
    print(f"  git commit -m 'chore: bump version to {new_version}'")
    print(f"  git push")


if __name__ == "__main__":
    main()
