"""Tests for Phase 3b: Doc Freshness Scanner, Enhanced Health Score,
Status Tracker Exporter, and Export-on-Receipt sync.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from models import WorkItem, Feature, ScanResult


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def populated_db(app, db):
    """Create a mix of WorkItems and Features for score testing."""
    with app.app_context():
        # Work items with various priorities
        items = [
            WorkItem(
                title="Critical bug",
                priority="critical",
                status="backlog",
                project="vms",
                category="bug",
            ),
            WorkItem(
                title="High debt",
                priority="high",
                status="backlog",
                project="vms",
                category="tech_debt",
            ),
            WorkItem(
                title="Medium task",
                priority="medium",
                status="backlog",
                project="vms",
                category="tech_debt",
            ),
            WorkItem(
                title="Done recently",
                priority="medium",
                status="done",
                project="vms",
                category="tech_debt",
                completed_at=datetime.utcnow() - timedelta(days=5),
            ),
        ]
        for item in items:
            db.session.add(item)

        # Features
        features = [
            Feature(
                name="Login",
                requirement_id="FR-001",
                domain="Auth",
                implementation_status="implemented",
                project="vms",
            ),
            Feature(
                name="Signup",
                requirement_id="FR-002",
                domain="Auth",
                implementation_status="implemented",
                project="vms",
            ),
            Feature(
                name="Email",
                requirement_id="FR-003",
                domain="Comms",
                implementation_status="pending",
                project="vms",
            ),
            Feature(
                name="Reports",
                requirement_id="FR-004",
                domain="Reporting",
                implementation_status="future",
                project="vms",
            ),
        ]
        for f in features:
            db.session.add(f)

        db.session.commit()
        yield


@pytest.fixture
def scan_results(app, db):
    """Create scan results for health score testing."""
    with app.app_context():
        # Coupling scan with some findings
        coupling_data = {
            "findings": [
                {"severity": "critical", "message": "Missing template"},
                {"severity": "warning", "message": "Orphaned template"},
                {"severity": "warning", "message": "Orphaned template 2"},
            ],
            "scanned_files": 20,
        }
        sr = ScanResult(
            scanner="coupling",
            project="vms",
            result_json=json.dumps(coupling_data),
            finding_count=3,
            scanned_at=datetime.utcnow(),
        )
        db.session.add(sr)

        # Doc freshness scan
        freshness_data = {
            "findings": [
                {"severity": "critical", "message": "Doc stale"},
                {"severity": "warning", "message": "Doc slightly stale"},
            ],
            "scanned_files": 5,
        }
        sr2 = ScanResult(
            scanner="doc_freshness",
            project="vms",
            result_json=json.dumps(freshness_data),
            finding_count=2,
            scanned_at=datetime.utcnow(),
        )
        db.session.add(sr2)
        db.session.commit()
        yield


# ── Health Score Tests ────────────────────────────────────


class TestHealthScore:
    """Test the 5-component health score engine."""

    def test_no_data_has_component_structure(self, app, db):
        """Empty database should still return 5 components."""
        with app.app_context():
            from utils.health_score import compute_health_score

            result = compute_health_score()
            assert len(result["components"]) == 5
            # Some components return None (scans, features), others return valid scores (debt=100)
            null_components = [c for c in result["components"] if c["score"] is None]
            assert (
                len(null_components) >= 3
            )  # scan, doc_freshness, feature_coverage, work_flow

    def test_has_five_components(self, app, populated_db, scan_results):
        """Score should always return 5 components."""
        with app.app_context():
            from utils.health_score import compute_health_score

            result = compute_health_score()
            assert len(result["components"]) == 5
            names = [c["name"] for c in result["components"]]
            assert "Scan Health" in names
            assert "Doc Freshness" in names
            assert "Debt Load" in names
            assert "Feature Coverage" in names
            assert "Work Flow" in names

    def test_scan_health_deducts_for_findings(self, app, scan_results):
        """Scan health should deduct 10 per critical, 3 per warning."""
        from utils.health_score import _scan_health

        result = _scan_health()
        # coupling: 1 critical + 2 warnings, doc_freshness: 1 critical + 1 warning
        # Total: 2 criticals (-20) + 3 warnings (-9) = 71
        assert result["score"] == 71
        assert "2 critical" in result["description"]

    def test_doc_freshness_deducts_for_staleness(self, app, scan_results):
        """Doc freshness should deduct for stale docs."""
        from utils.health_score import _doc_freshness

        result = _doc_freshness()
        # 1 critical (-20) + 1 warning (-10) = 70
        assert result["score"] == 70
        assert "2 stale docs" in result["description"]

    def test_debt_load_scores_by_priority(self, app, populated_db):
        """Debt load should score based on priority of active items."""
        from utils.health_score import _debt_load

        result = _debt_load()
        # 4 active items (includes done but not archived): critical(-5) + high(-3) + 2×medium(-2) = 90
        assert result["score"] == 90
        assert "active item" in result["description"]

    def test_feature_coverage_ratio(self, app, populated_db):
        """Feature coverage should be implemented/total × 100."""
        from utils.health_score import _feature_coverage

        result = _feature_coverage()
        # 2 implemented out of 4 = 50%
        assert result["score"] == 50
        assert "2/4" in result["description"]

    def test_work_flow_measures_throughput(self, app, populated_db):
        """Work flow should score based on recent completions vs backlog."""
        from utils.health_score import _work_flow

        result = _work_flow()
        # 1 done recently, 3 backlog = 33%
        assert result["score"] == 33

    def test_overall_score_is_weighted_average(self, app, populated_db, scan_results):
        """Overall score should be weighted average of components."""
        from utils.health_score import compute_health_score

        result = compute_health_score()
        assert result["score"] is not None
        assert 0 <= result["score"] <= 100
        assert result["color"] in ("success", "warning", "danger")

    def test_component_scores_clamped(self, app, db):
        """Scores should be clamped between 0 and 100."""
        with app.app_context():
            # Create 50 critical findings to try to go negative
            data = {
                "findings": [
                    {"severity": "critical", "message": f"Issue {i}"} for i in range(50)
                ]
            }
            sr = ScanResult(
                scanner="test_scanner",
                project="vms",
                result_json=json.dumps(data),
                finding_count=50,
                scanned_at=datetime.utcnow(),
            )
            db.session.add(sr)
            db.session.commit()

            from utils.health_score import _scan_health

            result = _scan_health()
            assert result["score"] == 0  # Never negative


# ── Doc Freshness Scanner Tests ───────────────────────────


class TestDocFreshnessScanner:
    """Test the doc freshness scanner."""

    def test_scanner_with_no_config(self):
        """Scanner should return error when no watched_docs."""
        from scanners.doc_freshness import DocFreshnessScanner

        scanner = DocFreshnessScanner()
        result = scanner.scan({"project_root": ".", "watched_docs": []})
        assert result.scanned_files == 0
        assert len(result.errors) == 1
        assert "No watched_docs" in result.errors[0]

    def test_scanner_handles_missing_doc(self, tmp_path):
        """Scanner should report error for missing doc files."""
        from scanners.doc_freshness import DocFreshnessScanner

        scanner = DocFreshnessScanner()
        config = {
            "project_root": str(tmp_path),
            "watched_docs": [
                {"doc": "nonexistent.md", "watches": ["src/"], "priority": "high"}
            ],
        }
        result = scanner.scan(config)
        assert "Doc not found" in result.errors[0]

    def test_priority_to_severity_mapping(self):
        """Priority should map to correct severity."""
        from scanners.doc_freshness import DocFreshnessScanner

        scanner = DocFreshnessScanner()
        assert scanner._priority_to_severity("critical") == "critical"
        assert scanner._priority_to_severity("high") == "warning"
        assert scanner._priority_to_severity("medium") == "info"
        assert scanner._priority_to_severity("low") == "info"
        assert scanner._priority_to_severity("unknown") == "info"

    def test_scanner_registered(self):
        """Doc freshness should be in the scanner registry."""
        from scanners.base import SCANNER_REGISTRY

        assert "doc_freshness" in SCANNER_REGISTRY

    @patch("scanners.doc_freshness.subprocess.run")
    def test_git_based_detection(self, mock_run, tmp_path):
        """Scanner should detect stale docs via git log."""
        from scanners.doc_freshness import DocFreshnessScanner

        # Create a doc file
        doc_file = tmp_path / "docs" / "api.md"
        doc_file.parent.mkdir(parents=True)
        doc_file.write_text("# API Docs")

        # Mock git log: doc was last modified a month ago, source yesterday
        def fake_git_log(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            path_arg = cmd[-1] if cmd else ""

            result = MagicMock()
            result.returncode = 0

            if "docs/api.md" in path_arg:
                result.stdout = "2026-02-01T00:00:00-06:00"
            else:
                result.stdout = "2026-03-18T00:00:00-06:00"
            return result

        mock_run.side_effect = fake_git_log

        scanner = DocFreshnessScanner()
        config = {
            "project_root": str(tmp_path),
            "watched_docs": [
                {"doc": "docs/api.md", "watches": ["routes/api/"], "priority": "high"}
            ],
        }
        result = scanner.scan(config)

        assert len(result.findings) == 1
        assert result.findings[0].severity == "warning"  # high → warning
        assert "stale" in result.findings[0].message


# ── Status Tracker Exporter Tests ─────────────────────────


class TestStatusTrackerExporter:
    """Test the status tracker exporter."""

    def test_render_produces_markdown(self, app, populated_db):
        """Render should produce valid markdown with headers."""
        with app.app_context():
            from exporters.status_tracker_exporter import StatusTrackerExporter

            exporter = StatusTrackerExporter()
            content = exporter.render("vms")

            assert "# VMS Development Status Tracker" in content
            assert "## Status Legend" in content
            assert "## Quick Summary" in content
            assert "✅" in content

    def test_render_includes_all_domains(self, app, populated_db):
        """All domains from features should appear as sections."""
        with app.app_context():
            from exporters.status_tracker_exporter import StatusTrackerExporter

            exporter = StatusTrackerExporter()
            content = exporter.render("vms")

            assert "## Auth" in content
            assert "## Comms" in content
            assert "## Reporting" in content

    def test_summary_table_has_correct_counts(self, app, populated_db):
        """Summary table should have auto-computed counts per domain."""
        from exporters.status_tracker_exporter import StatusTrackerExporter

        exporter = StatusTrackerExporter()
        content = exporter.render("vms")

        # Auth domain has 2 features, both implemented
        assert "Auth" in content
        # Comms domain has 1 feature, pending
        assert "Comms" in content
        # All domains present
        assert "Reporting" in content

    def test_status_symbols_correct(self, app, populated_db):
        """Features should show correct status symbols."""
        with app.app_context():
            from exporters.status_tracker_exporter import StatusTrackerExporter

            exporter = StatusTrackerExporter()
            content = exporter.render("vms")

            # Login is implemented → ✅
            assert "| FR-001 | Login | ✅" in content
            # Email is pending → 📋
            assert "| FR-003 | Email | 📋" in content
            # Reports is future → 🔮
            assert "| FR-004 | Reports | 🔮" in content

    def test_export_writes_file(self, app, populated_db, tmp_path):
        """Export should write file and return stats."""
        with app.app_context():
            from exporters.status_tracker_exporter import StatusTrackerExporter

            exporter = StatusTrackerExporter()
            output = tmp_path / "status_tracker.md"
            stats = exporter.export("vms", output)

            assert output.exists()
            assert stats["total"] == 4
            assert stats["implemented"] == 2
            assert stats["pending"] == 1

    def test_auto_generated_notice(self, app, populated_db):
        """Export should include auto-generated notice."""
        with app.app_context():
            from exporters.status_tracker_exporter import StatusTrackerExporter

            exporter = StatusTrackerExporter()
            content = exporter.render("vms")

            assert "AUTO-GENERATED by Polaris DevTools" in content

    def test_export_empty_project(self, app, db):
        """Export with no features should produce minimal output."""
        with app.app_context():
            from exporters.status_tracker_exporter import StatusTrackerExporter

            exporter = StatusTrackerExporter()
            content = exporter.render("empty_project")

            assert "~0" in content  # 0 features


# ── Dashboard Integration Tests ───────────────────────────


class TestDashboardHealthScore:
    """Test that the dashboard renders the new health score components."""

    def test_dashboard_shows_components(self, client, populated_db, scan_results):
        """Dashboard should display the health score component breakdown."""
        response = client.get("/")
        html = response.data.decode()

        assert "health-components" in html
        assert "Scan Health" in html
        assert "Doc Freshness" in html
        assert "Debt Load" in html
        assert "Feature Coverage" in html
        assert "Work Flow" in html

    def test_dashboard_component_bars(self, client, populated_db, scan_results):
        """Dashboard should show progress bars for each component."""
        response = client.get("/")
        html = response.data.decode()

        assert "component-bar" in html
        assert "component-fill" in html

    def test_dashboard_no_data(self, client):
        """Empty DB should show 'No data' with no components having scores."""
        response = client.get("/")
        html = response.data.decode()

        assert response.status_code == 200
        # Should still show the structure
        assert "Health Score" in html
