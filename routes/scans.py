"""Scan results and route registry routes."""

import json

from flask import Blueprint, render_template

from models import ScanResult

scans_bp = Blueprint("scans", __name__)


@scans_bp.route("/scans")
def scan_list():
    """Show scan result summary cards."""
    # Get latest result per scanner
    scanners = ["coupling", "security"]
    latest_scans = {}

    for scanner_name in scanners:
        result = (
            ScanResult.query.filter_by(scanner=scanner_name)
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )
        if result:
            data = json.loads(result.result_json) if result.result_json else {}
            latest_scans[scanner_name] = {
                "record": result,
                "findings": data.get("findings", []),
                "scanned_files": data.get("scanned_files", 0),
                "duration_ms": data.get("duration_ms", 0),
                "errors": data.get("errors", []),
            }

    return render_template(
        "scans.html",
        latest_scans=latest_scans,
    )


@scans_bp.route("/scans/<scanner_name>")
def scan_detail(scanner_name):
    """Show detailed findings for a specific scanner."""
    result = (
        ScanResult.query.filter_by(scanner=scanner_name)
        .order_by(ScanResult.scanned_at.desc())
        .first()
    )

    if not result:
        return render_template(
            "scan_detail.html",
            scanner_name=scanner_name,
            result=None,
            findings=[],
        )

    data = json.loads(result.result_json) if result.result_json else {}

    return render_template(
        "scan_detail.html",
        scanner_name=scanner_name,
        result=result,
        findings=data.get("findings", []),
        errors=data.get("errors", []),
        scanned_files=data.get("scanned_files", 0),
        duration_ms=data.get("duration_ms", 0),
    )


@scans_bp.route("/routes")
def route_list():
    """Show route registry from latest coupling scan."""
    result = (
        ScanResult.query.filter_by(scanner="coupling")
        .order_by(ScanResult.scanned_at.desc())
        .first()
    )

    registry = []
    if result and result.result_json:
        data = json.loads(result.result_json)
        registry = data.get("route_registry", [])

    return render_template(
        "routes.html",
        routes=registry,
        scanned_at=result.scanned_at if result else None,
    )
