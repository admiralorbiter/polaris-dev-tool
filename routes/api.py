"""API routes — health check and data endpoints."""

from flask import Blueprint, jsonify

from models import db, HealthSnapshot, ScanResult

api_bp = Blueprint("api", __name__)


@api_bp.route("/health")
def health():
    """Health check endpoint.

    Returns:
        JSON with status and basic system info.
    """
    try:
        # Verify DB connection
        db.session.execute(db.text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return jsonify(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
            "version": "0.1.0",
        }
    )


@api_bp.route("/trends/<project>")
def trends(project):
    """Return health score history and scan trend data for a project.

    Returns:
        JSON with 'health' (last 10 snapshots) and 'scans' (per-scanner counts).
    """
    # Health score trend — last 10 snapshots, oldest first for charting
    snapshots = (
        HealthSnapshot.query.filter_by(project=project)
        .order_by(HealthSnapshot.recorded_at.desc())
        .limit(10)
        .all()
    )
    health_trend = [
        {
            "date": s.recorded_at.strftime("%Y-%m-%d"),
            "time": s.recorded_at.strftime("%H:%M"),
            "score": s.score,
            "trigger": s.trigger,
        }
        for s in reversed(snapshots)  # chronological order for charts
    ]

    # Scan finding trend — last 10 runs per scanner
    scanner_names = ["coupling", "security", "doc_freshness"]
    scans_trend = {}
    for scanner_name in scanner_names:
        results = (
            ScanResult.query.filter_by(project=project, scanner=scanner_name)
            .order_by(ScanResult.scanned_at.desc())
            .limit(10)
            .all()
        )
        scans_trend[scanner_name] = [
            {
                "date": r.scanned_at.strftime("%Y-%m-%d"),
                "time": r.scanned_at.strftime("%H:%M"),
                "count": r.finding_count or 0,
                "severity": r.severity or "info",
            }
            for r in reversed(results)  # chronological order
        ]

    return jsonify(
        {
            "project": project,
            "health": health_trend,
            "scans": scans_trend,
        }
    )
