"""Dashboard routes — main landing page."""

from flask import Blueprint, render_template

from models import WorkItem, Feature, ScanResult, SessionLog
from utils.health_score import compute_health_score

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

    # Compute 5-component health score
    health = compute_health_score()

    # Last import timestamp
    last_import = WorkItem.query.order_by(WorkItem.updated_at.desc()).first()

    return render_template(
        "dashboard.html",
        stats=stats,
        health=health,
        last_import_at=last_import.updated_at if last_import else None,
    )
