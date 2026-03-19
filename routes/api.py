"""API routes — health check, data endpoints, and action endpoints."""

import json
from pathlib import Path

from flask import Blueprint, jsonify, request

from models import db, HealthSnapshot, ScanResult, SessionLog
from config_loader import load_all_project_configs

api_bp = Blueprint("api", __name__)


def _get_project_config(project_key):
    """Load a project config by key, or return None."""
    configs = load_all_project_configs()
    return configs.get(project_key)


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


# ─── Action Endpoints ─────────────────────────────────────────


@api_bp.route("/import/run", methods=["POST"])
def run_import():
    """Run data importers for a project.

    JSON body:
        project: str (required) — project key
        targets: list[str] (optional) — ["tech_debt", "status_tracker"] or omit for all

    Returns:
        JSON with import results per target.
    """
    data = request.get_json(silent=True) or {}
    project = data.get("project", "vms")
    targets = data.get("targets", ["tech_debt", "status_tracker"])

    config = _get_project_config(project)
    if not config:
        return (
            jsonify({"success": False, "message": f"Project '{project}' not found"}),
            404,
        )

    results = {}

    if "tech_debt" in targets:
        try:
            from importers.tech_debt_importer import TechDebtImporter

            # Resolve tech_debt.md path
            tech_debt_path = _resolve_managed_doc(config, "tech_debt")
            if tech_debt_path and tech_debt_path.exists():
                importer = TechDebtImporter()
                stats = importer.import_from_file(tech_debt_path, project=project)
                results["tech_debt"] = {"success": True, **stats}
            else:
                results["tech_debt"] = {
                    "success": False,
                    "message": "tech_debt.md not found",
                }
        except Exception as e:
            results["tech_debt"] = {"success": False, "message": str(e)}

    if "status_tracker" in targets:
        try:
            from importers.status_tracker_importer import StatusTrackerImporter

            tracker_path = _resolve_managed_doc(config, "status_tracker")
            if tracker_path and tracker_path.exists():
                importer = StatusTrackerImporter()
                stats = importer.import_from_file(tracker_path, project=project)
                results["status_tracker"] = {"success": True, **stats}
            else:
                results["status_tracker"] = {
                    "success": False,
                    "message": "development_status_tracker.md not found",
                }
        except Exception as e:
            results["status_tracker"] = {"success": False, "message": str(e)}

    return jsonify({"success": True, "results": results})


@api_bp.route("/scan/run", methods=["POST"])
def run_scan():
    """Run codebase scanners for a project.

    JSON body:
        project: str (required) — project key
        scanners: list[str] (optional) — scanner names, or omit for all

    Returns:
        JSON with scan results per scanner.
    """
    data = request.get_json(silent=True) or {}
    project = data.get("project", "vms")

    config = _get_project_config(project)
    if not config:
        return (
            jsonify({"success": False, "message": f"Project '{project}' not found"}),
            404,
        )

    from scanners import SCANNER_REGISTRY

    scanner_names = data.get("scanners", list(SCANNER_REGISTRY.keys()))
    results = {}

    for scanner_name in scanner_names:
        if scanner_name not in SCANNER_REGISTRY:
            results[scanner_name] = {"success": False, "message": "Scanner not found"}
            continue

        try:
            scanner_cls = SCANNER_REGISTRY[scanner_name]
            scanner_instance = scanner_cls()
            result = scanner_instance.scan(config)

            # Build result data (same format as CLI)
            result_data = {
                "findings": [
                    {
                        "file": f.file,
                        "line": f.line,
                        "message": f.message,
                        "severity": f.severity,
                        "details": f.details,
                    }
                    for f in result.findings
                ],
                "scanned_files": result.scanned_files,
                "errors": result.errors,
                "duration_ms": result.duration_ms,
            }
            if hasattr(result, "route_registry"):
                result_data["route_registry"] = result.route_registry

            severity = (
                "critical"
                if result.critical_count > 0
                else ("warning" if result.warning_count > 0 else "info")
            )

            # Store in DB
            scan_record = ScanResult(
                project=project,
                scanner=scanner_name,
                scanner_version=scanner_instance.version,
                severity=severity,
                finding_count=len(result.findings),
                result_json=json.dumps(result_data),
            )
            db.session.add(scan_record)

            results[scanner_name] = {
                "success": True,
                "finding_count": len(result.findings),
                "criticals": result.critical_count,
                "warnings": result.warning_count,
                "severity": severity,
            }
        except Exception as e:
            results[scanner_name] = {"success": False, "message": str(e)}

    db.session.commit()
    return jsonify({"success": True, "results": results})


@api_bp.route("/session/start", methods=["POST"])
def start_session():
    """Start a development session (generates briefing).

    JSON body:
        project: str (required) — project key

    Returns:
        JSON with session ID and briefing summary.
    """
    data = request.get_json(silent=True) or {}
    project = data.get("project", "vms")

    config = _get_project_config(project)
    if not config:
        return (
            jsonify({"success": False, "message": f"Project '{project}' not found"}),
            404,
        )

    # Check for existing active session
    active = (
        SessionLog.query.filter_by(project=project, ended_at=None)
        .order_by(SessionLog.started_at.desc())
        .first()
    )
    if active:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Session #{active.id} is already active. End it first.",
                    "session_id": active.id,
                }
            ),
            409,
        )

    from utils.briefing import generate_briefing

    project_root = str(config.project_root) if hasattr(config, "project_root") else None
    briefing_data = generate_briefing(project, project_root)

    # Create session log
    goal = data.get("goal", "").strip() or None
    initiative_id = data.get("initiative_id")

    session_log = SessionLog(
        project=project,
        goal=goal,
        initiative_id=int(initiative_id) if initiative_id else None,
        commit_range_start=briefing_data.get("commit_sha"),
        briefing_json=json.dumps(briefing_data),
    )
    db.session.add(session_log)
    db.session.commit()

    # Build a summary for the UI
    sections = briefing_data.get("sections", {})
    summary = {
        "critical_findings": len(sections.get("critical_findings", [])),
        "in_progress": len(sections.get("in_progress", [])),
        "upcoming_reviews": len(sections.get("upcoming_reviews", [])),
        "stale_docs": len(sections.get("doc_freshness", [])),
    }

    return jsonify(
        {
            "success": True,
            "session_id": session_log.id,
            "message": f"Session #{session_log.id} started",
            "summary": summary,
        }
    )


@api_bp.route("/session/end", methods=["POST"])
def end_session():
    """End the active development session (generates receipt).

    JSON body:
        project: str (required) — project key
        auto_export: bool (optional, default true) — auto-export dirty docs
        auto_drift: bool (optional, default true) — create drift work items

    Returns:
        JSON with receipt data, commit message, and session stats.
    """
    data = request.get_json(silent=True) or {}
    project = data.get("project", "vms")
    auto_export = data.get("auto_export", True)
    auto_drift = data.get("auto_drift", True)

    config = _get_project_config(project)
    if not config:
        return (
            jsonify({"success": False, "message": f"Project '{project}' not found"}),
            404,
        )

    # Find active session
    active_session = (
        SessionLog.query.filter_by(project=project, ended_at=None)
        .order_by(SessionLog.started_at.desc())
        .first()
    )
    if not active_session:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "No active session found. Start one first.",
                }
            ),
            404,
        )

    from utils.receipt import (
        generate_receipt,
        create_drift_work_items,
        generate_commit_message,
    )
    from utils.git_helpers import get_commit_sha
    from utils.briefing import _record_snapshot

    project_root = str(config.project_root) if hasattr(config, "project_root") else None
    start_sha = active_session.commit_range_start

    # Generate receipt
    receipt_data = generate_receipt(project, project_root, start_sha)

    # Post-receipt hooks
    drift_item_ids = []
    alerts = receipt_data.get("alerts", [])
    if auto_drift and alerts:
        drift_item_ids = create_drift_work_items(project, alerts)

    exported_docs = []
    if auto_export:
        try:
            from exporters.tech_debt_exporter import TechDebtExporter
            from exporters.status_tracker_exporter import StatusTrackerExporter
            from models import WorkItem, Feature

            exporters_map = {
                "tech_debt": (TechDebtExporter, WorkItem),
                "status_tracker": (StatusTrackerExporter, Feature),
            }
            for doc_key, managed in config.managed_docs.items():
                pair = exporters_map.get(doc_key)
                if not pair:
                    continue
                exporter_cls, model_cls = pair
                exporter = exporter_cls()
                latest = model_cls.query.order_by(model_cls.updated_at.desc()).first()
                if latest and exporter.is_dirty(project, doc_key, latest.updated_at):
                    output_path = Path(config.project_root) / managed.path
                    exporter.export(project, output_path)
                    exporter.git_stage(output_path, Path(config.project_root))
                    exported_docs.append(doc_key)
        except Exception:
            pass  # Non-fatal

    receipt_data["docs_exported"] = exported_docs

    # End session
    end_sha = get_commit_sha(project_root) if project_root else None
    active_session.end_session(end_sha)
    active_session.receipt_json = json.dumps(receipt_data)
    active_session.files_changed = json.dumps(
        receipt_data.get("layers", {}).get("1", {}).get("files", [])
    )
    active_session.docs_exported = json.dumps(exported_docs)
    db.session.commit()

    # Record health snapshot
    _record_snapshot(project, trigger="receipt")

    # Generate commit message
    commit_msg = generate_commit_message(receipt_data)

    return jsonify(
        {
            "success": True,
            "session_id": active_session.id,
            "duration_minutes": active_session.duration_minutes,
            "message": f"Session #{active_session.id} ended ({active_session.duration_minutes}m)",
            "receipt": {
                "layers": receipt_data.get("layers", {}),
                "alerts": alerts,
                "summary": receipt_data.get("summary", ""),
                "drift_items_created": len(drift_item_ids),
                "docs_exported": exported_docs,
            },
            "commit_message": commit_msg,
        }
    )


# ─── Helpers ──────────────────────────────────────────────────


def _resolve_managed_doc(config, doc_key):
    """Resolve the file path for a managed doc, with fallbacks."""
    # Try managed_docs config first
    managed = config.managed_docs.get(doc_key)
    if managed:
        path = Path(config.project_root) / managed.path
        if path.exists():
            return path

    # Fallback paths
    root = Path(config.project_root)
    fallbacks = {
        "tech_debt": [
            root / "documentation" / "content" / "developer" / "tech_debt.md",
            root / "docs" / "tech_debt.md",
            root / "tech_debt.md",
        ],
        "status_tracker": [
            root
            / "documentation"
            / "content"
            / "developer"
            / "development_status_tracker.md",
            root / "docs" / "development_status_tracker.md",
            root / "development_status_tracker.md",
        ],
    }
    for candidate in fallbacks.get(doc_key, []):
        if candidate.exists():
            return candidate

    return None


# --- Exporter Registry ---

EXPORTER_REGISTRY = {}


def _register_exporters():
    """Lazily register known exporters."""
    if EXPORTER_REGISTRY:
        return
    from exporters.tech_debt_exporter import TechDebtExporter
    from exporters.status_tracker_exporter import StatusTrackerExporter
    from exporters.changelog_exporter import ChangelogExporter
    from exporters.hybrid_exporter import HybridDocExporter

    EXPORTER_REGISTRY["tech_debt_v1"] = TechDebtExporter
    EXPORTER_REGISTRY["status_tracker_v1"] = StatusTrackerExporter
    EXPORTER_REGISTRY["changelog_v1"] = ChangelogExporter
    EXPORTER_REGISTRY["hybrid_v1"] = HybridDocExporter


@api_bp.route("/export/sync", methods=["POST"])
def export_sync():
    """Sync all dirty managed documents for a project.

    Iterates ManagedDoc records where is_dirty=True, runs the matching
    exporter, writes the file, and clears the dirty flag.

    Request JSON:
        {"project": "vms"}  (optional, defaults to "vms")

    Returns:
        JSON with exported doc keys and any skipped docs.
    """
    from datetime import datetime, timezone
    from models import ManagedDoc

    data = request.get_json(silent=True) or {}
    project = data.get("project", "vms")
    config = _get_project_config(project)
    if not config:
        return jsonify({"error": f"Unknown project: {project}"}), 404

    _register_exporters()

    dirty_docs = ManagedDoc.query.filter_by(project=project, is_dirty=True).all()

    exported = []
    skipped = []
    errors = []

    for doc in dirty_docs:
        exporter_cls = EXPORTER_REGISTRY.get(doc.exporter_key)
        if not exporter_cls:
            skipped.append(doc.doc_key)
            continue

        try:
            exporter = exporter_cls()
            output_path = _resolve_output_path(config, doc)

            if hasattr(exporter, "export"):
                exporter.export(project, output_path, config)
            else:
                content = exporter.render(project, config)
                exporter.write_file(content, output_path)
                exporter.record_export(project, doc.doc_key, str(output_path), 0)

            doc.is_dirty = False
            doc.last_exported_at = datetime.now(timezone.utc)
            exported.append(doc.doc_key)
        except Exception as e:
            errors.append({"doc": doc.doc_key, "error": str(e)})

    db.session.commit()

    return jsonify(
        {
            "exported": exported,
            "skipped": skipped,
            "errors": errors,
            "total_dirty": len(dirty_docs),
        }
    )


def _resolve_output_path(config, doc):
    """Resolve the output path for a managed doc.

    Uses the doc.output_path relative to the project root.
    Falls back to the existing fallback logic for known doc keys.
    """
    root = Path(config.get("project_root", "."))

    if doc.output_path:
        return root / doc.output_path

    # Fallback for legacy docs
    return root / f"{doc.doc_key}.md"


# --- Doc Seeding ---

# Default managed doc definitions
DEFAULT_MANAGED_DOCS = [
    {
        "doc_key": "tech_debt",
        "title": "Tech Debt Tracker",
        "tier": "generated",
        "exporter_key": "tech_debt_v1",
        "output_path": "documentation/content/developer/tech_debt.md",
    },
    {
        "doc_key": "status_tracker",
        "title": "Development Status Tracker",
        "tier": "generated",
        "exporter_key": "status_tracker_v1",
        "output_path": "documentation/content/developer/development_status_tracker.md",
    },
    {
        "doc_key": "changelog",
        "title": "Changelog",
        "tier": "generated",
        "exporter_key": "changelog_v1",
        "output_path": "documentation/content/developer/changelog.md",
    },
]


@api_bp.route("/docs/seed", methods=["POST"])
def docs_seed():
    """Seed the standard managed doc records.

    Creates ManagedDoc entries if they don't already exist.
    Idempotent — safe to call multiple times.

    Request JSON:
        {"project": "vms"}  (optional, defaults to "vms")
    """
    from models import ManagedDoc

    data = request.get_json(silent=True) or {}
    project = data.get("project", "vms")

    created = []
    existing = []

    for doc_def in DEFAULT_MANAGED_DOCS:
        existing_doc = ManagedDoc.query.filter_by(
            project=project, doc_key=doc_def["doc_key"]
        ).first()

        if existing_doc:
            existing.append(doc_def["doc_key"])
            continue

        doc = ManagedDoc(
            project=project,
            doc_key=doc_def["doc_key"],
            title=doc_def["title"],
            tier=doc_def["tier"],
            exporter_key=doc_def["exporter_key"],
            output_path=doc_def.get("output_path"),
            template_path=doc_def.get("template_path"),
            is_dirty=True,
        )
        db.session.add(doc)
        created.append(doc_def["doc_key"])

    db.session.commit()

    return jsonify(
        {
            "created": created,
            "existing": existing,
            "total": len(DEFAULT_MANAGED_DOCS),
        }
    )


# --- Feature Import ---


@api_bp.route("/features/import", methods=["POST"])
def features_import():
    """Bulk import features (upsert by requirement_id).

    Request JSON:
        {
            "project": "vms",
            "features": [
                {"requirement_id": "FR-VIRTUAL-001", "name": "...",
                 "domain": "Virtual Events", "implementation_status": "implemented",
                 "notes": "..."}
            ]
        }
    """
    from models import Feature, ManagedDoc

    data = request.get_json(silent=True) or {}
    project = data.get("project", "vms")
    features_data = data.get("features", [])

    if not features_data:
        return jsonify({"error": "No features provided"}), 400

    created = 0
    updated = 0
    skipped = 0

    for feat_data in features_data:
        req_id = feat_data.get("requirement_id", "").strip()
        name = feat_data.get("name", "").strip()

        if not req_id or not name:
            skipped += 1
            continue

        existing = Feature.query.filter_by(requirement_id=req_id).first()

        if existing:
            # Update existing feature
            existing.name = name
            existing.domain = feat_data.get("domain", existing.domain)
            existing.implementation_status = feat_data.get(
                "implementation_status", existing.implementation_status
            )
            if feat_data.get("notes"):
                existing.notes = feat_data["notes"]
            updated += 1
        else:
            # Create new feature
            feature = Feature(
                project=project,
                requirement_id=req_id,
                name=name,
                domain=feat_data.get("domain"),
                implementation_status=feat_data.get("implementation_status", "pending"),
                notes=feat_data.get("notes"),
            )
            db.session.add(feature)
            created += 1

    # Mark status tracker as dirty
    doc = ManagedDoc.query.filter_by(project=project, doc_key="status_tracker").first()
    if doc:
        doc.is_dirty = True

    db.session.commit()

    return jsonify(
        {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total": len(features_data),
        }
    )
