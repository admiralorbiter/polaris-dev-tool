"""Dashboard routes — main landing page."""

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

    return render_template("dashboard.html", stats=stats)
