"""Git utility functions using subprocess.

Provides git state, commit SHAs, and diff-aware file lists
without requiring GitPython as a dependency.
"""

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str | Path) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_git_state(project_root: str | Path) -> dict:
    """Get current git state for briefing.

    Returns:
        dict with:
            - branch: str (current branch name)
            - dirty: bool (uncommitted changes exist)
            - untracked: int (count of untracked files)
            - ahead: int (commits ahead of origin)
            - behind: int (commits behind origin)
            - available: bool (True if git is accessible)
    """
    root = str(project_root)

    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    if not branch:
        return {
            "branch": "",
            "dirty": False,
            "untracked": 0,
            "ahead": 0,
            "behind": 0,
            "available": False,
        }

    # Dirty check
    dirty = bool(
        _run_git(["diff", "--quiet"], root) == ""
        and subprocess.run(
            ["git", "diff", "--quiet"], cwd=root, capture_output=True
        ).returncode
        != 0
    )

    # Untracked files
    untracked_output = _run_git(["ls-files", "--others", "--exclude-standard"], root)
    untracked = len(untracked_output.splitlines()) if untracked_output else 0

    # Ahead/behind origin
    ahead = 0
    behind = 0
    tracking = _run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root
    )
    if tracking:
        ahead_output = _run_git(["rev-list", "--count", f"{tracking}..HEAD"], root)
        behind_output = _run_git(["rev-list", "--count", f"HEAD..{tracking}"], root)
        ahead = int(ahead_output) if ahead_output.isdigit() else 0
        behind = int(behind_output) if behind_output.isdigit() else 0

    return {
        "branch": branch,
        "dirty": dirty,
        "untracked": untracked,
        "ahead": ahead,
        "behind": behind,
        "available": True,
    }


def get_commit_sha(project_root: str | Path) -> str | None:
    """Get current HEAD commit SHA."""
    sha = _run_git(["rev-parse", "HEAD"], str(project_root))
    return sha if sha else None


def get_changed_files(
    project_root: str | Path, start_sha: str, end_sha: str | None = None
) -> list[str]:
    """Get list of files changed between two commits.

    Args:
        project_root: Path to the git repo root.
        start_sha: Start commit SHA.
        end_sha: End commit SHA (default: HEAD).

    Returns:
        List of changed file paths (relative to repo root).
    """
    root = str(project_root)
    if end_sha is None:
        end_sha = "HEAD"

    output = _run_git(["diff", "--name-only", start_sha, end_sha], root)
    if not output:
        return []
    return [line for line in output.splitlines() if line.strip()]


def get_recent_commit_message(project_root: str | Path) -> str:
    """Get the most recent commit message (subject line only)."""
    return _run_git(["log", "-1", "--format=%s"], str(project_root))
