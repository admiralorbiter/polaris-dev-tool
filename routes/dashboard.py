"""Dashboard routes — main landing page."""

import json

from flask import Blueprint, render_template

from models import WorkItem, Feature, ScanResult, SessionLog

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Dashboard home page with project health overview."""
    # Gather summary stats for the dashboard
    stats = {
        "work_items": {
            "total": WorkItem.query.filter_by(is_archived=False).count(),
            "in_progress": WorkItem.query.filter_by(
                status="in_progress", is_archived=False
            ).count(),
            "backlog": WorkItem.query.filter_by(
                status="backlog", is_archived=False
            ).count(),
            "done": WorkItem.query.filter_by(status="done").count(),
        },
        "features": {
            "total": Feature.query.count(),
            "implemented": Feature.query.filter_by(
                implementation_status="implemented"
            ).count(),
            "pending": Feature.query.filter_by(implementation_status="pending").count(),
            "partial": Feature.query.filter_by(implementation_status="partial").count(),
        },
        "scans": {
            "latest": ScanResult.query.order_by(ScanResult.scanned_at.desc()).first(),
        },
        "sessions": {
            "latest": SessionLog.query.order_by(SessionLog.started_at.desc()).first(),
            "total": SessionLog.query.count(),
        },
    }

    # Compute health score from latest scan results
    health = _compute_health_score()

    # Last import timestamp
    last_import = WorkItem.query.order_by(WorkItem.updated_at.desc()).first()

    return render_template(
        "dashboard.html",
        stats=stats,
        health=health,
        last_import_at=last_import.updated_at if last_import else None,
    )


def _compute_health_score() -> dict:
    """Calculate a 0-100 health score from scan findings.

    Scoring: start at 100, deduct 10 per critical, 3 per warning.
    Returns dict with score, label, and color class.
    """
    scans = ScanResult.query.order_by(ScanResult.scanned_at.desc()).all()
    if not scans:
        return {"score": None, "label": "No data", "color": "muted"}

    # Use latest result per scanner
    seen = set()
    criticals = 0
    warnings = 0
    for scan in scans:
        if scan.scanner in seen:
            continue
        seen.add(scan.scanner)
        if scan.result_json:
            data = json.loads(scan.result_json)
            for f in data.get("findings", []):
                if f.get("severity") == "critical":
                    criticals += 1
                elif f.get("severity") == "warning":
                    warnings += 1

    score = max(0, 100 - (criticals * 10) - (warnings * 3))

    if score >= 80:
        return {"score": score, "label": "Good", "color": "success"}
    elif score >= 50:
        return {"score": score, "label": "Needs Work", "color": "warning"}
    else:
        return {"score": score, "label": "Critical", "color": "danger"}
