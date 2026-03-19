"""Health Score Engine — 5-component weighted health assessment.

Components:
1. Scan Health    (20%) — Based on scan findings (criticals, warnings)
2. Doc Freshness  (20%) — Based on stale doc count from doc_freshness scanner
3. Debt Load      (20%) — Based on active tech debt volume and priority
4. Feature Coverage (20%) — Ratio of implemented features to total
5. Work Flow      (20%) — Ratio of items completed recently vs active backlog
"""

import json
from datetime import datetime, timedelta

from models import WorkItem, Feature, ScanResult


def compute_health_score() -> dict:
    """Calculate a 5-component health score (0–100 each, weighted average).

    Returns:
        dict with:
            - score: int (0–100) or None
            - label: str ("Good", "Needs Work", "Critical", "No data")
            - color: str ("success", "warning", "danger", "muted")
            - components: list of dicts with name, score, weight, description
    """
    components = [
        _scan_health(),
        _doc_freshness(),
        _debt_load(),
        _feature_coverage(),
        _work_flow(),
    ]

    # Check if we have any data at all
    scored = [c for c in components if c["score"] is not None]
    if not scored:
        return {
            "score": None,
            "label": "No data",
            "color": "muted",
            "components": components,
        }

    # Weighted average (equal weights, 20% each)
    total_weight = sum(c["weight"] for c in scored)
    weighted_sum = sum(c["score"] * c["weight"] for c in scored)
    score = round(weighted_sum / total_weight) if total_weight > 0 else 0

    # Determine label and color
    if score >= 80:
        label, color = "Good", "success"
    elif score >= 50:
        label, color = "Needs Work", "warning"
    else:
        label, color = "Critical", "danger"

    return {
        "score": score,
        "label": label,
        "color": color,
        "components": components,
    }


def _scan_health() -> dict:
    """Component 1: Score based on scan findings.

    Formula: 100 − (10 × criticals) − (3 × warnings), clamped to [0, 100].
    """
    scans = ScanResult.query.order_by(ScanResult.scanned_at.desc()).all()
    if not scans:
        return _component("Scan Health", None, 0.2, "No scans run yet")

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
                sev = f.get("severity", "")
                if sev == "critical":
                    criticals += 1
                elif sev == "warning":
                    warnings += 1

    score = max(0, min(100, 100 - (criticals * 10) - (warnings * 3)))
    desc = f"{criticals} critical, {warnings} warnings"
    return _component("Scan Health", score, 0.2, desc)


def _doc_freshness() -> dict:
    """Component 2: Score based on stale documentation.

    Uses the latest doc_freshness scan results.
    Formula: 100 − (20 × critical stale) − (10 × high stale) − (5 × medium stale).
    """
    scan = (
        ScanResult.query.filter_by(scanner="doc_freshness")
        .order_by(ScanResult.scanned_at.desc())
        .first()
    )
    if not scan or not scan.result_json:
        return _component("Doc Freshness", None, 0.2, "No freshness scan run yet")

    data = json.loads(scan.result_json)
    findings = data.get("findings", [])

    criticals = sum(1 for f in findings if f.get("severity") == "critical")
    warnings = sum(1 for f in findings if f.get("severity") == "warning")
    infos = sum(1 for f in findings if f.get("severity") == "info")

    score = max(0, min(100, 100 - (criticals * 20) - (warnings * 10) - (infos * 5)))
    total_stale = criticals + warnings + infos
    desc = (
        f"{total_stale} stale doc{'s' if total_stale != 1 else ''}"
        if total_stale
        else "All docs fresh"
    )
    return _component("Doc Freshness", score, 0.2, desc)


def _debt_load() -> dict:
    """Component 3: Score based on active tech debt volume.

    Formula: 100 − (5 × critical items) − (3 × high items) − (1 × medium items).
    """
    active_items = WorkItem.query.filter_by(is_archived=False).all()
    if not active_items:
        return _component("Debt Load", 100, 0.2, "No active items")

    critical_count = sum(1 for i in active_items if i.priority == "critical")
    high_count = sum(1 for i in active_items if i.priority == "high")
    medium_count = sum(1 for i in active_items if i.priority == "medium")

    score = max(
        0, min(100, 100 - (critical_count * 5) - (high_count * 3) - (medium_count * 1))
    )
    total = len(active_items)
    desc = f"{total} active item{'s' if total != 1 else ''}"
    return _component("Debt Load", score, 0.2, desc)


def _feature_coverage() -> dict:
    """Component 4: Ratio of implemented features to total.

    Formula: (implemented / total) × 100.
    """
    total = Feature.query.count()
    if total == 0:
        return _component("Feature Coverage", None, 0.2, "No features tracked")

    implemented = Feature.query.filter_by(implementation_status="implemented").count()
    score = round((implemented / total) * 100)
    desc = f"{implemented}/{total} implemented"
    return _component("Feature Coverage", score, 0.2, desc)


def _work_flow() -> dict:
    """Component 5: Work completion flow.

    Ratio of recently completed items (last 30 days) to total active backlog.
    Higher = better throughput.
    """
    active = WorkItem.query.filter_by(is_archived=False, status="backlog").count()
    cutoff = datetime.utcnow() - timedelta(days=30)
    completed_recently = WorkItem.query.filter(
        WorkItem.status == "done",
        WorkItem.completed_at >= cutoff,
    ).count()

    if active == 0 and completed_recently == 0:
        return _component("Work Flow", None, 0.2, "No work item activity")

    # Score: ratio-based. If you complete more than your backlog, score is 100.
    if active == 0:
        score = 100
    else:
        ratio = completed_recently / active
        score = min(100, round(ratio * 100))

    desc = f"{completed_recently} done / {active} backlog (30d)"
    return _component("Work Flow", score, 0.2, desc)


def _component(name: str, score: int | None, weight: float, description: str) -> dict:
    """Build a component dict."""
    return {
        "name": name,
        "score": score,
        "weight": weight,
        "description": description,
    }
