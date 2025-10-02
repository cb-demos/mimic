#!/usr/bin/env python3
"""
Cleanup script for identifying and deleting old, unused CloudBees components.

This script operates in two modes:

ANALYZE MODE (default):
1. Lists all components at org/suborg level in CloudBees Unify
2. Checks workflow run history for each component
3. Filters for components with no runs OR last run older than specified days
4. Outputs candidates to CSV file for manual review

DELETE MODE (--delete-from):
1. Reads CSV file with component candidates
2. Deletes components (and optionally GitHub repos)
3. Requires confirmation before deletion
"""

import argparse
import asyncio
import csv
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, ".")

from src.config import settings
from src.gh import GitHubClient
from src.unify import UnifyAPIClient


def parse_iso_date(date_str: str | None) -> datetime | None:
    """Parse ISO format date string to datetime object."""
    if not date_str:
        return None
    try:
        # Handle various ISO formats
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError):
        return None


def extract_repo_from_url(repo_url: str) -> tuple[str, str] | None:
    """Extract owner and repo name from GitHub URL."""
    if not repo_url:
        return None

    # Handle both .git and non-.git URLs
    repo_url = repo_url.rstrip("/").replace(".git", "")

    # Extract from https://github.com/owner/repo format
    if "github.com/" in repo_url:
        parts = repo_url.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]

    return None


def write_candidates_to_csv(
    candidates: list[dict[str, Any]], output_file: str, org_id: str
) -> None:
    """Write candidates to CSV file for manual review."""
    fieldnames = [
        "org_id",
        "component_id",
        "component_name",
        "repo_url",
        "github_owner",
        "github_repo",
        "run_count",
        "last_commit_date",
        "days_since_last_commit",
        "reason",
    ]

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for candidate in candidates:
            repo_info = candidate.get("repo_info")
            last_commit_date = candidate.get("last_commit_date")

            row = {
                "org_id": org_id,
                "component_id": candidate["id"],
                "component_name": candidate["name"],
                "repo_url": candidate["repo_url"],
                "github_owner": repo_info[0] if repo_info else "",
                "github_repo": repo_info[1] if repo_info else "",
                "run_count": candidate["run_count"],
                "last_commit_date": last_commit_date.isoformat() if last_commit_date else "",
                "days_since_last_commit": (
                    (datetime.now(timezone.utc) - last_commit_date).days
                    if last_commit_date
                    else ""
                ),
                "reason": candidate["reason"],
            }
            writer.writerow(row)


def read_candidates_from_csv(input_file: str) -> tuple[str, list[dict[str, Any]]]:
    """Read candidates from CSV file. Returns (org_id, candidates)."""
    candidates = []
    org_id = None

    with open(input_file, "r", newline="") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            # Extract org_id from first row
            if org_id is None:
                org_id = row["org_id"]

            # Parse last_commit_date back to datetime if present
            last_commit_date = None
            if row.get("last_commit_date"):
                last_commit_date = datetime.fromisoformat(row["last_commit_date"])

            # Reconstruct repo_info tuple
            repo_info = None
            if row["github_owner"] and row["github_repo"]:
                repo_info = (row["github_owner"], row["github_repo"])

            candidate = {
                "id": row["component_id"],
                "name": row["component_name"],
                "repo_url": row["repo_url"],
                "repo_info": repo_info,
                "run_count": int(row["run_count"]) if row["run_count"] else 0,
                "last_commit_date": last_commit_date,
                "reason": row["reason"],
            }
            candidates.append(candidate)

    return org_id, candidates


async def analyze_components(
    org_id: str,
    unify_api_key: str,
    github_token: str,
    age_days: int = 30,
    rate_limit_delay: float = 0.5,
) -> list[dict[str, Any]]:
    """
    Analyze components and return list of those meeting deletion criteria.

    NEW LOGIC:
    - Components WITH runs: Skip (keep them for now)
    - Components with NO runs: Check GitHub last commit date
      - If last commit > age_days ago: candidate for deletion

    Args:
        org_id: CloudBees organization ID
        unify_api_key: CloudBees API key
        github_token: GitHub token for repo date checking
        age_days: Minimum days since last activity for deletion consideration
        rate_limit_delay: Seconds to wait between API calls

    Returns:
        List of component dictionaries with analysis data
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=age_days)

    print(f"Analyzing components in organization {org_id}...")
    print(f"Looking for components with:")
    print(f"  • Zero workflow runs")
    print(f"  • AND last GitHub commit older than {age_days} days (before {cutoff_date.date()})")
    print()

    # Get all components
    gh_client = GitHubClient(github_token)

    with UnifyAPIClient(api_key=unify_api_key) as unify_client:
        response = unify_client.list_components(org_id)
        components = response.get("service", [])

        print(f"Found {len(components)} total components")
        print(f"Checking run history and GitHub activity (with {rate_limit_delay}s delay between requests)...")
        print()

        # Analyze each component
        candidates = []
        for idx, component in enumerate(components, 1):
            component_id = component.get("id")
            component_name = component.get("name", "Unknown")
            repo_url = component.get("repositoryUrl", "")

            print(f"[{idx}/{len(components)}] {component_name}")
            print(f"  ID: {component_id}")
            print(f"  Repository: {repo_url}")

            # Get runs for this component
            try:
                runs_response = unify_client.list_runs(org_id, component_id)
                runs = runs_response.get("runs", [])
                run_count = len(runs)
                pagination = runs_response.get("pagination", {})
                total_count = pagination.get("base", {}).get("resultCount", run_count)

                print(f"  Total Runs: {total_count}")

                # NEW LOGIC: Skip components with any runs
                if total_count > 0:
                    print(f"  ❌ Not a candidate (has workflow runs)")
                    print()
                    if idx < len(components):
                        time.sleep(rate_limit_delay)
                    continue

                # Component has zero runs - check GitHub for last commit
                repo_info = extract_repo_from_url(repo_url)
                if not repo_info:
                    print(f"  ⚠️  Cannot parse GitHub repo URL, skipping")
                    print()
                    if idx < len(components):
                        time.sleep(rate_limit_delay)
                    continue

                owner, repo = repo_info
                try:
                    repo_data = await gh_client.get_repo(owner, repo)
                    if not repo_data:
                        print(f"  ⚠️  Cannot fetch GitHub repo data, skipping")
                        print()
                        if idx < len(components):
                            time.sleep(rate_limit_delay)
                        continue

                    # Check last push date
                    last_commit_date = parse_iso_date(repo_data.get("pushed_at"))
                    if not last_commit_date:
                        print(f"  ⚠️  Cannot determine last commit date, skipping")
                        print()
                        if idx < len(components):
                            time.sleep(rate_limit_delay)
                        continue

                    days_since_commit = (datetime.now(timezone.utc) - last_commit_date).days
                    print(f"  Last Commit: {last_commit_date.date()} ({days_since_commit} days ago)")

                    # Check if old enough
                    if last_commit_date < cutoff_date:
                        reason = f"No runs and last commit {days_since_commit} days ago"
                        print(f"  ✅ Candidate: {reason}")
                        candidates.append(
                            {
                                "id": component_id,
                                "name": component_name,
                                "repo_url": repo_url,
                                "repo_info": repo_info,
                                "run_count": total_count,
                                "last_run_date": None,
                                "last_commit_date": last_commit_date,
                                "reason": reason,
                            }
                        )
                    else:
                        print(f"  ❌ Not a candidate (last commit too recent)")

                except Exception as e:
                    print(f"  ⚠️  Error fetching GitHub data: {e}")

            except Exception as e:
                print(f"  ⚠️  Error fetching runs: {e}")

            print()

            # Rate limiting
            if idx < len(components):
                time.sleep(rate_limit_delay)

    return candidates


async def delete_components(
    org_id: str,
    unify_api_key: str,
    github_token: str,
    candidates: list[dict[str, Any]],
    delete_repos: bool = False,
    repos_only: bool = False,
    deletion_delay: float = 1.0,
) -> tuple[int, int]:
    """
    Delete components and optionally their GitHub repositories.

    Args:
        org_id: CloudBees organization ID
        unify_api_key: CloudBees API key
        github_token: GitHub token
        candidates: List of components to delete
        delete_repos: Whether to also delete GitHub repos
        repos_only: Only delete GitHub repos, skip Unify components
        deletion_delay: Seconds to wait between deletions

    Returns:
        Tuple of (successful_deletions, failed_deletions)
    """
    success_count = 0
    failure_count = 0

    gh_client = GitHubClient(github_token)

    with UnifyAPIClient(api_key=unify_api_key) as unify_client:
        for idx, candidate in enumerate(candidates, 1):
            component_id = candidate["id"]
            component_name = candidate["name"]
            repo_url = candidate["repo_url"]
            repo_info = candidate["repo_info"]

            print(f"[{idx}/{len(candidates)}] Processing: {component_name}")

            try:
                # Delete component from CloudBees (unless repos-only mode)
                if not repos_only:
                    print(f"  Deleting CloudBees component: {component_id}...")
                    unify_client.delete_component(org_id, component_id)
                    print(f"  ✅ Component deleted")
                    success_count += 1

                # Delete GitHub repository if requested
                if (delete_repos or repos_only) and repo_info:
                    owner, repo = repo_info
                    repo_full_name = f"{owner}/{repo}"
                    print(f"  Deleting GitHub repository: {repo_full_name}...")

                    try:
                        await gh_client.delete_repository(repo_full_name)
                        print(f"  ✅ Repository deleted")
                    except Exception as e:
                        print(f"  ❌ Failed to delete repository: {e}")

            except Exception as e:
                print(f"  ❌ Failed to delete component: {e}")
                failure_count += 1

            print()

            # Rate limiting between deletions
            if idx < len(candidates):
                time.sleep(deletion_delay)

    return success_count, failure_count


async def main():
    parser = argparse.ArgumentParser(
        description="Cleanup old, unused CloudBees components and associated GitHub repos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze and output to CSV (default mode)
  %(prog)s 2f05829d-ea2c-429e-7d3b-98ba87db3776 --output cleanup-candidates.csv

  # Delete components from CSV (prompts for confirmation)
  %(prog)s --delete-from cleanup-candidates.csv

  # Delete components AND GitHub repos (after manual review of CSV)
  %(prog)s --delete-from cleanup-candidates.csv --delete-repos

  # Delete ONLY GitHub repos (when components already cleaned up in Unify)
  %(prog)s --delete-from cleanup-candidates.csv --repos-only

  # Dry run to see what would be deleted
  %(prog)s --delete-from cleanup-candidates.csv --dry-run

  # Custom deletion delay to avoid rate limits
  %(prog)s --delete-from cleanup-candidates.csv --deletion-delay 2.0
        """,
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "org_id", nargs="?", help="CloudBees organization ID (for analyze mode)"
    )
    mode_group.add_argument(
        "--delete-from",
        metavar="CSV_FILE",
        help="Delete components from CSV file (delete mode)",
    )

    # Analyze mode options
    parser.add_argument(
        "--age-days",
        type=int,
        default=30,
        help="Minimum days since last run for deletion consideration (default: 30)",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=0.5,
        help="Seconds to wait between API requests (default: 0.5)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="cleanup-candidates.csv",
        help="Output CSV file for candidates (default: cleanup-candidates.csv)",
    )

    # Delete mode options
    parser.add_argument(
        "--delete-repos",
        action="store_true",
        help="Also delete associated GitHub repositories",
    )
    parser.add_argument(
        "--repos-only",
        action="store_true",
        help="Only delete GitHub repositories, skip Unify components (use when already cleaned up in Unify)",
    )
    parser.add_argument(
        "--deletion-delay",
        type=float,
        default=1.0,
        help="Seconds to wait between deletions (default: 1.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    # Credentials
    parser.add_argument(
        "--unify-api-key",
        default=settings.UNIFY_API_KEY,
        help="CloudBees API key (defaults to UNIFY_API_KEY env var)",
    )
    parser.add_argument(
        "--github-token",
        default=settings.GITHUB_TOKEN,
        help="GitHub token (defaults to GITHUB_TOKEN env var)",
    )

    args = parser.parse_args()

    # Validate required credentials
    if not args.unify_api_key:
        print("Error: UNIFY_API_KEY environment variable or --unify-api-key required")
        sys.exit(1)

    if not args.github_token:
        print("Error: GITHUB_TOKEN environment variable or --github-token required")
        sys.exit(1)

    print("=" * 80)
    print("CloudBees Component Cleanup Tool")
    print("=" * 80)
    print()

    # ANALYZE MODE
    if args.org_id:
        print("MODE: Analyze")
        print()

        # Analyze components
        candidates = await analyze_components(
            org_id=args.org_id,
            unify_api_key=args.unify_api_key,
            github_token=args.github_token,
            age_days=args.age_days,
            rate_limit_delay=args.rate_limit_delay,
        )

        if not candidates:
            print("✅ No components found matching deletion criteria")
            return

        # Write to CSV
        write_candidates_to_csv(candidates, args.output, args.org_id)

        # Summary
        print("=" * 80)
        print(f"SUMMARY: Found {len(candidates)} component(s) for deletion")
        print("=" * 80)
        print()
        print(f"Results written to: {args.output}")
        print()
        print("Review the CSV file, then run:")
        print(f"  {Path(sys.argv[0]).name} --delete-from {args.output}")
        print()

    # DELETE MODE
    elif args.delete_from:
        print("MODE: Delete")
        print()

        # Read candidates from CSV
        if not Path(args.delete_from).exists():
            print(f"Error: File not found: {args.delete_from}")
            sys.exit(1)

        org_id, candidates = read_candidates_from_csv(args.delete_from)

        if not candidates:
            print("✅ No components found in CSV file")
            return

        if not org_id:
            print("Error: CSV file missing org_id column")
            sys.exit(1)

        # Summary
        print("=" * 80)
        print(f"LOADED: {len(candidates)} component(s) from {args.delete_from}")
        print(f"Organization ID: {org_id}")
        print("=" * 80)
        print()

        for candidate in candidates:
            print(f"  • {candidate['name']}")
            print(f"    - Reason: {candidate['reason']}")
            print(f"    - Total Runs: {candidate['run_count']}")
            if candidate.get("last_commit_date"):
                print(f"    - Last Commit: {candidate['last_commit_date'].date()}")
            print(f"    - Repository: {candidate['repo_url']}")
            print()

        if args.dry_run:
            print("🔍 DRY RUN - No changes will be made")
            return

        # Confirmation prompt
        if args.repos_only:
            print("⚠️  WARNING: This will permanently delete ONLY the GitHub repositories")
            print("⚠️  CloudBees components will NOT be touched")
        else:
            print("⚠️  WARNING: This will permanently delete the components listed above")
            if args.delete_repos:
                print("⚠️  WARNING: This will ALSO delete the associated GitHub repositories")
        print()

        response = input("Type 'DELETE' to confirm deletion: ")
        if response != "DELETE":
            print("Deletion cancelled")
            return

        print()
        print("=" * 80)
        print("Deleting components...")
        print("=" * 80)
        print()

        success, failure = await delete_components(
            org_id=org_id,
            unify_api_key=args.unify_api_key,
            github_token=args.github_token,
            candidates=candidates,
            delete_repos=args.delete_repos,
            repos_only=args.repos_only,
            deletion_delay=args.deletion_delay,
        )

        print("=" * 80)
        print(f"COMPLETED: {success} deleted, {failure} failed")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())