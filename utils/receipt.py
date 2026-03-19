"""Post-session receipt engine — the 9-layer change matrix.

Classifies every file changed during a dev session into 9 layers,
detects documentation drift (Layer 7), and generates alerts.
"""

from datetime import date

from models import db, WorkItem
from utils.git_helpers import get_changed_files, get_commit_sha


# ── Layer Classification ─────────────────────────────────────

LAYER_DEFINITIONS = {
    1: {"name": "Files Changed", "description": "All changed files"},
    2: {"name": "Routes Added/Modified", "description": "Route handler changes"},
    3: {"name": "Models Touched", "description": "Database model changes"},
    4: {"name": "Templates Changed", "description": "HTML template changes"},
    5: {"name": "Tests Added/Modified", "description": "Test file changes"},
    6: {"name": "Services Affected", "description": "Service layer changes"},
    7: {"name": "Docs Updated", "description": "Documentation changes"},
    8: {"name": "Dependencies Changed", "description": "Package dependency changes"},
    9: {"name": "Config Changes", "description": "Configuration file changes"},
}


def classify_files(changed_files: list[str]) -> dict[int, list[str]]:
    """Classify changed files into 9 layers.

    A file can appear in multiple layers (e.g., a route file is both
    Layer 1 and Layer 2).

    Returns:
        dict mapping layer number → list of file paths.
    """
    layers = {i: [] for i in range(1, 10)}

    for filepath in changed_files:
        # Normalize path separators for cross-platform
        fp = filepath.replace("\\", "/")
        parts = fp.split("/")
        basename = parts[-1] if parts else fp

        # Layer 1: Every changed file
        layers[1].append(fp)

        # Layer 2: Routes — Python files in routes/ or containing route patterns
        if any(p == "routes" for p in parts) and fp.endswith(".py"):
            layers[2].append(fp)

        # Layer 3: Models — files in models/ or models.py
        if (
            any(p == "models" for p in parts) or basename == "models.py"
        ) and fp.endswith(".py"):
            layers[3].append(fp)

        # Layer 4: Templates — HTML files in templates/
        if any(p == "templates" for p in parts) and fp.endswith(".html"):
            layers[4].append(fp)

        # Layer 5: Tests — files in tests/
        if any(p == "tests" for p in parts) and fp.endswith(".py"):
            layers[5].append(fp)

        # Layer 6: Services — files in services/
        if any(p == "services" for p in parts) and fp.endswith(".py"):
            layers[6].append(fp)

        # Layer 7: Docs — markdown files in docs/, documentation/, or top-level *.md
        if fp.endswith(".md"):
            if (
                any(p in ("docs", "documentation") for p in parts)
                or len(parts) == 1  # top-level .md
            ):
                layers[7].append(fp)

        # Layer 8: Dependencies
        if basename in (
            "requirements.txt",
            "package.json",
            "package-lock.json",
            "Pipfile",
            "Pipfile.lock",
            "pyproject.toml",
            "poetry.lock",
        ):
            layers[8].append(fp)

        # Layer 9: Config
        if basename in (
            ".env",
            ".env.example",
            "config.py",
            "config.yaml",
            "config.yml",
            ".flake8",
            ".gitignore",
            "setup.cfg",
        ) or (fp.endswith((".yaml", ".yml")) and any(p == "projects" for p in parts)):
            layers[9].append(fp)

    return layers


# ── Drift Detection (Layer 7) ────────────────────────────────


def detect_drift(layers: dict[int, list[str]]) -> list[dict]:
    """Detect documentation drift — code changed but docs not updated.

    Checks:
    1. Routes changed but no docs updated → alert
    2. Models changed but no docs updated → alert
    3. Code changed but no tests changed → warning

    Returns:
        List of alert dicts with type, message, and suggested action.
    """
    alerts = []

    code_changed = bool(layers[2] or layers[3] or layers[6])
    docs_changed = bool(layers[7])
    tests_changed = bool(layers[5])

    # Drift: code changed but no docs
    if code_changed and not docs_changed:
        changed_areas = []
        if layers[2]:
            changed_areas.append(f"{len(layers[2])} route(s)")
        if layers[3]:
            changed_areas.append(f"{len(layers[3])} model(s)")
        if layers[6]:
            changed_areas.append(f"{len(layers[6])} service(s)")

        alerts.append(
            {
                "type": "drift",
                "severity": "warning",
                "message": (
                    f"Code changed ({', '.join(changed_areas)}) "
                    "but no documentation updated"
                ),
                "action": "Review and export managed docs",
            }
        )

    # Warning: code changed but no tests
    if code_changed and not tests_changed:
        alerts.append(
            {
                "type": "coverage",
                "severity": "info",
                "message": "Code changed but no test files were modified",
                "action": "Consider adding tests for new code",
            }
        )

    # Routes added without templates
    if layers[2] and not layers[4]:
        alerts.append(
            {
                "type": "coupling",
                "severity": "info",
                "message": (
                    f"{len(layers[2])} route file(s) changed "
                    "but no templates were modified"
                ),
                "action": "Verify template coverage with coupling scanner",
            }
        )

    return alerts


# ── Receipt Generation ────────────────────────────────────────


def generate_receipt(
    project: str,
    project_root: str | None,
    start_sha: str | None,
) -> dict:
    """Generate a post-session receipt with 9-layer matrix.

    Args:
        project: Project key.
        project_root: Path to the git repo.
        start_sha: Commit SHA from the briefing (session start).

    Returns:
        dict with layers, alerts, summary, and end_sha.
    """
    end_sha = get_commit_sha(project_root) if project_root else None

    # Get changed files
    if project_root and start_sha and end_sha and start_sha != end_sha:
        changed_files = get_changed_files(project_root, start_sha, end_sha)
    else:
        changed_files = []

    # Also include uncommitted changes (staged + unstaged)
    if project_root:
        from utils.git_helpers import _run_git

        staged = _run_git(["diff", "--cached", "--name-only"], str(project_root))
        unstaged = _run_git(["diff", "--name-only"], str(project_root))
        working = set(changed_files)
        if staged:
            working.update(staged.splitlines())
        if unstaged:
            working.update(unstaged.splitlines())
        changed_files = sorted(working)

    # Classify
    layers = classify_files(changed_files)

    # Drift detection
    alerts = detect_drift(layers)

    # Summary
    summary = _build_summary(layers)

    return {
        "project": project,
        "start_sha": start_sha,
        "end_sha": end_sha,
        "total_files": len(changed_files),
        "layers": {
            str(num): {
                "name": LAYER_DEFINITIONS[num]["name"],
                "files": files,
                "count": len(files),
            }
            for num, files in layers.items()
        },
        "alerts": alerts,
        "summary": summary,
    }


def _build_summary(layers: dict[int, list[str]]) -> str:
    """Build a one-line summary from layer counts."""
    parts = []
    if layers[2]:
        parts.append(f"{len(layers[2])} routes")
    if layers[3]:
        parts.append(f"{len(layers[3])} models")
    if layers[4]:
        parts.append(f"{len(layers[4])} templates")
    if layers[5]:
        parts.append(f"{len(layers[5])} tests")
    if layers[7]:
        parts.append(f"{len(layers[7])} docs")
    if layers[8]:
        parts.append(f"{len(layers[8])} deps")

    total = len(layers[1])
    detail = ", ".join(parts) if parts else "no categorized changes"
    return f"{total} files changed ({detail})"


# ── Post-Receipt Hooks ────────────────────────────────────────


def create_drift_work_items(project: str, alerts: list[dict]) -> list[int]:
    """Create work items for drift alerts.

    Returns:
        List of created WorkItem IDs.
    """
    created_ids = []

    for alert in alerts:
        if alert["type"] != "drift":
            continue

        # Check for existing drift item today (avoid duplicates)
        today_source_id = f"DRIFT-{date.today().isoformat()}"
        existing = WorkItem.query.filter_by(
            project=project, source_id=today_source_id
        ).first()
        if existing:
            continue

        item = WorkItem(
            project=project,
            source_id=today_source_id,
            title=f"Update docs — {alert['message'][:80]}",
            category="review",
            priority="medium",
            status="backlog",
            notes=(
                f"Auto-created by session receipt.\n\n"
                f"{alert['message']}\n\n"
                f"Action: {alert['action']}"
            ),
        )
        db.session.add(item)
        db.session.flush()  # Get ID before commit
        created_ids.append(item.id)

    return created_ids


def generate_commit_message(receipt: dict) -> str:
    """Generate a commit message from receipt data.

    Returns:
        Multi-line commit message string.
    """
    layers = receipt.get("layers", {})
    total = receipt.get("total_files", 0)

    if total == 0:
        return "chore: session with no file changes"

    # Determine type from changes
    has_routes = layers.get("2", {}).get("count", 0) > 0
    has_tests = layers.get("5", {}).get("count", 0) > 0
    has_docs = layers.get("7", {}).get("count", 0) > 0
    has_deps = layers.get("8", {}).get("count", 0) > 0

    if has_routes:
        prefix = "feat"
    elif has_tests:
        prefix = "test"
    elif has_docs:
        prefix = "docs"
    elif has_deps:
        prefix = "chore"
    else:
        prefix = "refactor"

    # Subject line
    summary = receipt.get("summary", f"{total} files changed")
    subject = f"{prefix}: {summary}"

    # Body
    body_lines = []
    for layer_num in range(1, 10):
        layer = layers.get(str(layer_num), {})
        count = layer.get("count", 0)
        if count > 0 and layer_num != 1:  # Skip layer 1 (redundant with total)
            name = layer.get("name", f"Layer {layer_num}")
            files = layer.get("files", [])
            body_lines.append(f"- {name}: {', '.join(files[:5])}")
            if len(files) > 5:
                body_lines.append(f"  ... and {len(files) - 5} more")

    # Alerts
    alerts = receipt.get("alerts", [])
    if alerts:
        body_lines.append("")
        body_lines.append("Alerts:")
        for alert in alerts:
            body_lines.append(f"- ⚠ {alert['message']}")

    body = "\n".join(body_lines)
    return f"{subject}\n\n{body}" if body else subject
