"""Pre-session briefing engine.

Generates a 6-point project health snapshot:
1. Git state (branch, dirty, ahead/behind)
2. Critical scan findings
3. In-progress work items
4. Upcoming feature reviews (next 14 days)
5. Doc freshness alerts
6. Managed doc export status
"""

import json
import logging
from datetime import date, timedelta

from models import WorkItem, Feature, ScanResult, ExportLog, HealthSnapshot, db
from utils.git_helpers import get_git_state, get_commit_sha
from utils.health_score import compute_health_score

logger = logging.getLogger(__name__)


def generate_briefing(project: str, project_root: str | None = None) -> dict:
    """Generate a pre-session briefing.

    Args:
        project: Project key (e.g., 'vms').
        project_root: Path to the project git repo (for git state).

    Returns:
        dict with 6 briefing sections + metadata.
    """
    sections = {}

    # 1. Git state
    if project_root:
        sections["git_state"] = get_git_state(project_root)
    else:
        sections["git_state"] = {"available": False}

    # 2. Critical scan findings
    sections["critical_findings"] = _get_critical_findings(project)

    # 3. In-progress work items
    sections["in_progress"] = _get_in_progress_items(project)

    # 4. Upcoming reviews
    sections["upcoming_reviews"] = _get_upcoming_reviews(project)

    # 5. Doc freshness alerts
    sections["doc_freshness"] = _get_doc_freshness(project)

    # 6. Managed doc export status
    sections["export_status"] = _get_export_status(project)

    # Metadata
    commit_sha = get_commit_sha(project_root) if project_root else None

    result = {
        "project": project,
        "commit_sha": commit_sha,
        "sections": sections,
    }

    # Record a health snapshot for trend tracking
    _record_snapshot(project, trigger="briefing")

    return result


def _record_snapshot(project: str, trigger: str = "briefing") -> None:
    """Record a HealthSnapshot for trend tracking.

    Args:
        project: Project key.
        trigger: 'briefing' or 'receipt'.
    """
    try:
        score_data = compute_health_score()
        snap = HealthSnapshot(
            project=project,
            score=score_data["total"],
            components_json=json.dumps(score_data.get("components", {})),
            trigger=trigger,
        )
        db.session.add(snap)
        db.session.commit()
    except Exception as exc:
        # Non-fatal: never let snapshot recording break the briefing
        logger.warning("HealthSnapshot recording failed (trigger=%s): %s", trigger, exc)
        try:
            db.session.rollback()
        except Exception:
            pass


def _get_critical_findings(project: str) -> list[dict]:
    """Get critical/warning scan findings from latest scan per scanner."""
    scanners = ["coupling", "security", "doc_freshness"]
    findings = []

    for scanner_name in scanners:
        scan = (
            ScanResult.query.filter_by(project=project, scanner=scanner_name)
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )
        if not scan or not scan.result_json:
            continue

        data = json.loads(scan.result_json)
        for f in data.get("findings", []):
            if f.get("severity") in ("critical", "warning"):
                findings.append(
                    {
                        "scanner": scanner_name,
                        "severity": f["severity"],
                        "file": f.get("file", ""),
                        "message": f.get("message", ""),
                    }
                )

    return findings


def _get_in_progress_items(project: str) -> list[dict]:
    """Get work items currently in progress."""
    items = WorkItem.query.filter_by(
        project=project, status="in_progress", is_archived=False
    ).all()

    return [
        {
            "id": item.id,
            "source_id": item.source_id,
            "title": item.title,
            "priority": item.priority,
            "category": item.category,
        }
        for item in items
    ]


def _get_upcoming_reviews(project: str) -> list[dict]:
    """Get features due for review within 14 days."""
    cutoff = date.today() + timedelta(days=14)
    features = Feature.query.filter(
        Feature.project == project,
        Feature.next_review.isnot(None),
        Feature.next_review <= cutoff,
    ).all()

    today = date.today()
    return [
        {
            "id": f.id,
            "name": f.name,
            "requirement_id": f.requirement_id,
            "days_until": (f.next_review - today).days,
            "overdue": f.next_review < today,
        }
        for f in features
    ]


def _get_doc_freshness(project: str) -> list[dict]:
    """Get doc freshness alerts from latest scan."""
    scan = (
        ScanResult.query.filter_by(project=project, scanner="doc_freshness")
        .order_by(ScanResult.scanned_at.desc())
        .first()
    )
    if not scan or not scan.result_json:
        return []

    data = json.loads(scan.result_json)
    return [
        {
            "file": f.get("file", ""),
            "severity": f.get("severity", "info"),
            "message": f.get("message", ""),
        }
        for f in data.get("findings", [])
        if f.get("severity") in ("critical", "warning")
    ]


def _get_export_status(project: str) -> list[dict]:
    """Get managed doc export status (dirty count)."""
    results = []

    # Check tech_debt export status
    latest_export = (
        ExportLog.query.filter_by(project=project, target="tech_debt")
        .order_by(ExportLog.exported_at.desc())
        .first()
    )
    latest_update = (
        WorkItem.query.filter_by(project=project)
        .order_by(WorkItem.updated_at.desc())
        .first()
    )

    if latest_update:
        is_dirty = (
            not latest_export or latest_update.updated_at > latest_export.exported_at
        )
        results.append(
            {
                "doc": "tech_debt",
                "dirty": is_dirty,
                "last_export": (
                    latest_export.exported_at.isoformat() if latest_export else None
                ),
            }
        )

    # Check status_tracker export status (Feature uses last_activity, not updated_at)
    latest_export = (
        ExportLog.query.filter_by(project=project, target="status_tracker")
        .order_by(ExportLog.exported_at.desc())
        .first()
    )

    feature_count = Feature.query.filter_by(project=project).count()
    if feature_count > 0:
        # Feature doesn't have updated_at; use last_activity or assume dirty if no export
        is_dirty = not latest_export  # Conservative: dirty if never exported
        if not is_dirty:
            # Check if any feature was modified (last_activity) after last export
            latest_feature = (
                Feature.query.filter_by(project=project)
                .filter(Feature.last_activity.isnot(None))
                .order_by(Feature.last_activity.desc())
                .first()
            )
            if latest_feature and latest_feature.last_activity:
                is_dirty = latest_feature.last_activity > latest_export.exported_at

        results.append(
            {
                "doc": "status_tracker",
                "dirty": is_dirty,
                "last_export": (
                    latest_export.exported_at.isoformat() if latest_export else None
                ),
            }
        )

    return results
