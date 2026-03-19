"""Scan results and route registry routes."""

import json

from flask import Blueprint, render_template

from models import ScanResult

scans_bp = Blueprint("scans", __name__)


@scans_bp.route("/scans")
def scan_list():
    """Show scan result summary cards."""
    from scanners import SCANNER_REGISTRY

    latest_scans = {}

    for scanner_name in SCANNER_REGISTRY:
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

    # Trend data — last 10 runs for mini-chart
    past_runs = (
        ScanResult.query.filter_by(scanner=scanner_name)
        .order_by(ScanResult.scanned_at.desc())
        .limit(10)
        .all()
    )
    trend_data = [
        {
            "date": r.scanned_at.strftime("%m/%d"),
            "count": r.finding_count or 0,
            "severity": r.severity or "info",
        }
        for r in reversed(past_runs)
    ]

    return render_template(
        "scan_detail.html",
        scanner_name=scanner_name,
        result=result,
        findings=data.get("findings", []),
        errors=data.get("errors", []),
        scanned_files=data.get("scanned_files", 0),
        duration_ms=data.get("duration_ms", 0),
        trend_data=trend_data,
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


@scans_bp.route("/scans/<scanner_name>/context")
def scan_context(scanner_name):
    """Return AI context packet for a scanner's findings as JSON."""
    from flask import jsonify

    from utils.context_formatter import format_finding_context

    result = (
        ScanResult.query.filter_by(scanner=scanner_name)
        .order_by(ScanResult.scanned_at.desc())
        .first()
    )

    if not result or not result.result_json:
        return jsonify({"text": "No scan results available."})

    data = json.loads(result.result_json)
    findings = sorted(data.get("findings", []), key=lambda f: f.get("file", ""))

    # Get project root from config
    from config_loader import load_all_project_configs

    configs = load_all_project_configs()
    project_root = None
    if result.project in configs:
        project_root = getattr(configs[result.project], "project_root", None)

    context_blocks = []
    for f in findings:
        block = format_finding_context(f, scanner_name, project_root)
        context_blocks.append(block)

    full_text = (
        f"# {scanner_name.title()} Scanner — AI Context Packet\n"
        f"_{len(findings)} findings._\n\n---\n\n" + "\n---\n\n".join(context_blocks)
    )

    return jsonify({"text": full_text})
