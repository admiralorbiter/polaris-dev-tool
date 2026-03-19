"""Dashboard routes — main landing page."""

import json
from datetime import date, timedelta

from flask import Blueprint, render_template

from models import WorkItem, Feature, ScanResult, SessionLog, HealthSnapshot
from utils.health_score import compute_health_score

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Dashboard home page with project health overview."""
    # Detect fresh install — show setup wizard if DB is empty
    is_fresh_install = (
        WorkItem.query.count() == 0
        and Feature.query.count() == 0
        and ScanResult.query.count() == 0
    )

    # Active session for session controls
    active_session = (
        SessionLog.query.filter_by(ended_at=None)
        .order_by(SessionLog.started_at.desc())
        .first()
    )

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
        "sessions": {
            "latest": SessionLog.query.order_by(SessionLog.started_at.desc()).first(),
            "total": SessionLog.query.count(),
        },
    }

    # Per-scanner latest results for drill-down cards
    scanner_names = ["coupling", "security", "doc_freshness"]
    scanner_cards = []
    for name in scanner_names:
        result = (
            ScanResult.query.filter_by(scanner=name)
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )
        if result:
            data = json.loads(result.result_json) if result.result_json else {}
            findings = data.get("findings", [])
            criticals = sum(1 for f in findings if f.get("severity") == "critical")
            warnings = sum(1 for f in findings if f.get("severity") == "warning")
            scanner_cards.append(
                {
                    "name": name,
                    "display_name": name.replace("_", " ").title(),
                    "finding_count": len(findings),
                    "criticals": criticals,
                    "warnings": warnings,
                    "severity": result.severity or "info",
                    "scanned_at": result.scanned_at,
                }
            )

    # Feature review queue — due within 14 days or overdue
    review_cutoff = date.today() + timedelta(days=14)
    reviews_due = Feature.query.filter(
        Feature.next_review.isnot(None),
        Feature.next_review <= review_cutoff,
    ).count()
    reviews_overdue = Feature.query.filter(
        Feature.next_review.isnot(None),
        Feature.next_review < date.today(),
    ).count()

    # Health score trend — last 10 snapshots for sparkline
    snapshots = (
        HealthSnapshot.query.order_by(HealthSnapshot.recorded_at.desc()).limit(10).all()
    )
    health_trend = [
        {"score": s.score, "date": s.recorded_at.strftime("%m/%d")}
        for s in reversed(snapshots)
    ]

    # Combined scan finding trend — total findings per scan run (last 10)
    scan_trend = []
    seen_times = set()
    all_scans = ScanResult.query.order_by(ScanResult.scanned_at.desc()).limit(30).all()
    # Group by approximate time (hourly buckets) to avoid duplicate bars
    for sr in reversed(all_scans):
        bucket = sr.scanned_at.strftime("%Y-%m-%d %H")
        if bucket not in seen_times:
            seen_times.add(bucket)
            scan_trend.append(
                {
                    "date": sr.scanned_at.strftime("%m/%d"),
                    "count": sr.finding_count or 0,
                }
            )
    scan_trend = scan_trend[-10:]  # last 10 buckets

    # Compute 5-component health score
    health = compute_health_score()

    # Last import timestamp
    last_import = WorkItem.query.order_by(WorkItem.updated_at.desc()).first()

    return render_template(
        "dashboard.html",
        stats=stats,
        health=health,
        scanner_cards=scanner_cards,
        reviews_due=reviews_due,
        reviews_overdue=reviews_overdue,
        last_import_at=last_import.updated_at if last_import else None,
        health_trend=health_trend,
        scan_trend=scan_trend,
        is_fresh_install=is_fresh_install,
        active_session=active_session,
    )
