"""Tests for Phase 4b: Session Loop.

Covers:
- Git helpers (mocked subprocess)
- Briefing engine (6-point checklist)
- Receipt engine (9-layer matrix, drift detection, commit message)
- Session routes (list, detail)
- Dashboard sessions panel
"""

import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from models import db as _db, WorkItem, ScanResult, SessionLog


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Provide a database session."""
    with app.app_context():
        yield _db


# ── Git Helpers ────────────────────────────────────────────


class TestGitHelpers:
    """Test utils/git_helpers.py with mocked subprocess."""

    @patch("utils.git_helpers.subprocess.run")
    def test_get_git_state_available(self, mock_run, app):
        """Git state returns correct data when git is available."""
        from utils.git_helpers import get_git_state

        def side_effect(args, **kwargs):
            cmd = " ".join(args)
            result = MagicMock()
            result.returncode = 0

            if "rev-parse --abbrev-ref HEAD" in cmd:
                result.stdout = "main\n"
            elif "diff --quiet" in cmd:
                result.returncode = 1  # dirty
            elif "ls-files --others" in cmd:
                result.stdout = "file1.py\nfile2.py\n"
            elif "--symbolic-full-name" in cmd:
                result.stdout = "origin/main\n"
            elif "rev-list --count" in cmd and "..HEAD" in cmd:
                result.stdout = "3\n"
            elif "rev-list --count" in cmd and "HEAD.." in cmd:
                result.stdout = "1\n"
            else:
                result.stdout = ""
            return result

        mock_run.side_effect = side_effect

        state = get_git_state("/fake/path")
        assert state["available"] is True
        assert state["branch"] == "main"
        assert state["untracked"] == 2

    @patch("utils.git_helpers.subprocess.run")
    def test_get_git_state_unavailable(self, mock_run, app):
        """Git state returns unavailable when git command fails."""
        from utils.git_helpers import get_git_state

        mock_run.return_value = MagicMock(returncode=1, stdout="")
        state = get_git_state("/fake/path")
        assert state["available"] is False

    @patch("utils.git_helpers.subprocess.run")
    def test_get_commit_sha(self, mock_run, app):
        """get_commit_sha returns HEAD SHA."""
        from utils.git_helpers import get_commit_sha

        mock_run.return_value = MagicMock(returncode=0, stdout="abc123def456\n")
        sha = get_commit_sha("/fake/path")
        assert sha == "abc123def456"

    @patch("utils.git_helpers.subprocess.run")
    def test_get_commit_sha_unavailable(self, mock_run, app):
        """get_commit_sha returns None when git fails."""
        from utils.git_helpers import get_commit_sha

        mock_run.return_value = MagicMock(returncode=1, stdout="")
        sha = get_commit_sha("/fake/path")
        assert sha is None

    @patch("utils.git_helpers.subprocess.run")
    def test_get_changed_files(self, mock_run, app):
        """get_changed_files returns list of file paths."""
        from utils.git_helpers import get_changed_files

        mock_run.return_value = MagicMock(
            returncode=0, stdout="routes/foo.py\ntemplates/bar.html\n"
        )
        files = get_changed_files("/fake/path", "abc", "def")
        assert len(files) == 2
        assert "routes/foo.py" in files

    @patch("utils.git_helpers.subprocess.run")
    def test_get_changed_files_empty(self, mock_run, app):
        """get_changed_files returns empty list when no changes."""
        from utils.git_helpers import get_changed_files

        mock_run.return_value = MagicMock(returncode=0, stdout="")
        files = get_changed_files("/fake/path", "abc", "def")
        assert files == []


# ── Receipt — 9-Layer Classification ──────────────────────


class TestLayerClassification:
    """Test the 9-layer file classification logic."""

    def test_layer_1_all_files(self, app):
        """Layer 1 captures all changed files."""
        from utils.receipt import classify_files

        files = ["foo.py", "bar.html", "baz.md"]
        layers = classify_files(files)
        assert len(layers[1]) == 3

    def test_layer_2_routes(self, app):
        """Layer 2 captures route files."""
        from utils.receipt import classify_files

        layers = classify_files(["routes/dashboard.py", "models.py"])
        assert "routes/dashboard.py" in layers[2]
        assert "models.py" not in layers[2]

    def test_layer_3_models(self, app):
        """Layer 3 captures model files."""
        from utils.receipt import classify_files

        layers = classify_files(["models.py", "models/user.py", "routes/foo.py"])
        assert "models.py" in layers[3]
        assert "models/user.py" in layers[3]
        assert "routes/foo.py" not in layers[3]

    def test_layer_4_templates(self, app):
        """Layer 4 captures HTML templates."""
        from utils.receipt import classify_files

        layers = classify_files(["templates/base.html", "static/style.css"])
        assert "templates/base.html" in layers[4]
        assert "static/style.css" not in layers[4]

    def test_layer_5_tests(self, app):
        """Layer 5 captures test files."""
        from utils.receipt import classify_files

        layers = classify_files(["tests/test_foo.py", "routes/bar.py"])
        assert "tests/test_foo.py" in layers[5]

    def test_layer_6_services(self, app):
        """Layer 6 captures service files."""
        from utils.receipt import classify_files

        layers = classify_files(["services/auth.py", "routes/foo.py"])
        assert "services/auth.py" in layers[6]

    def test_layer_7_docs(self, app):
        """Layer 7 captures documentation files."""
        from utils.receipt import classify_files

        layers = classify_files(["docs/api.md", "README.md", "routes/foo.py"])
        assert "docs/api.md" in layers[7]
        assert "README.md" in layers[7]

    def test_layer_8_dependencies(self, app):
        """Layer 8 captures dependency files."""
        from utils.receipt import classify_files

        layers = classify_files(["requirements.txt", "package.json", "routes/foo.py"])
        assert "requirements.txt" in layers[8]
        assert "package.json" in layers[8]

    def test_layer_9_config(self, app):
        """Layer 9 captures config files."""
        from utils.receipt import classify_files

        layers = classify_files([".env", "config.py", ".gitignore", "routes/foo.py"])
        assert ".env" in layers[9]
        assert "config.py" in layers[9]
        assert ".gitignore" in layers[9]

    def test_file_in_multiple_layers(self, app):
        """A route file appears in both Layer 1 and Layer 2."""
        from utils.receipt import classify_files

        layers = classify_files(["routes/api.py"])
        assert "routes/api.py" in layers[1]
        assert "routes/api.py" in layers[2]

    def test_empty_file_list(self, app):
        """Empty file list produces empty layers."""
        from utils.receipt import classify_files

        layers = classify_files([])
        for i in range(1, 10):
            assert layers[i] == []

    def test_windows_path_handling(self, app):
        """Windows-style backslash paths are handled."""
        from utils.receipt import classify_files

        layers = classify_files(["routes\\dashboard.py"])
        assert "routes/dashboard.py" in layers[2]


# ── Drift Detection ───────────────────────────────────────


class TestDriftDetection:
    """Test Layer 7 drift detection logic."""

    def test_drift_code_changed_no_docs(self, app):
        """Alert when routes changed but no docs updated."""
        from utils.receipt import detect_drift

        layers = {i: [] for i in range(1, 10)}
        layers[2] = ["routes/api.py"]  # route changed
        alerts = detect_drift(layers)
        assert any(a["type"] == "drift" for a in alerts)

    def test_no_drift_when_docs_updated(self, app):
        """No drift alert when docs are also updated."""
        from utils.receipt import detect_drift

        layers = {i: [] for i in range(1, 10)}
        layers[2] = ["routes/api.py"]
        layers[7] = ["docs/api.md"]  # docs also changed
        alerts = detect_drift(layers)
        assert not any(a["type"] == "drift" for a in alerts)

    def test_coverage_warning_no_tests(self, app):
        """Info alert when code changed but no tests changed."""
        from utils.receipt import detect_drift

        layers = {i: [] for i in range(1, 10)}
        layers[2] = ["routes/api.py"]
        alerts = detect_drift(layers)
        assert any(a["type"] == "coverage" for a in alerts)

    def test_no_alerts_docs_only(self, app):
        """No alerts when only docs changed."""
        from utils.receipt import detect_drift

        layers = {i: [] for i in range(1, 10)}
        layers[1] = ["docs/readme.md"]
        layers[7] = ["docs/readme.md"]
        alerts = detect_drift(layers)
        assert len(alerts) == 0


# ── Commit Message Generator ─────────────────────────────


class TestCommitMessageGenerator:
    """Test commit message generation from receipt data."""

    def test_feat_prefix_with_routes(self, app):
        """Routes changed → 'feat' prefix."""
        from utils.receipt import generate_commit_message

        receipt = {
            "total_files": 3,
            "summary": "3 files changed (2 routes, 1 template)",
            "layers": {
                "2": {
                    "name": "Routes",
                    "count": 2,
                    "files": ["routes/a.py", "routes/b.py"],
                },
            },
            "alerts": [],
        }
        msg = generate_commit_message(receipt)
        assert msg.startswith("feat:")

    def test_test_prefix_with_tests(self, app):
        """Only tests changed → 'test' prefix."""
        from utils.receipt import generate_commit_message

        receipt = {
            "total_files": 1,
            "summary": "1 files changed (1 tests)",
            "layers": {
                "5": {"name": "Tests", "count": 1, "files": ["tests/test_a.py"]},
            },
            "alerts": [],
        }
        msg = generate_commit_message(receipt)
        assert msg.startswith("test:")

    def test_chore_for_no_files(self, app):
        """No files changed → chore message."""
        from utils.receipt import generate_commit_message

        receipt = {"total_files": 0, "layers": {}, "alerts": []}
        msg = generate_commit_message(receipt)
        assert "chore" in msg


# ── Briefing Engine ───────────────────────────────────────


class TestBriefingEngine:
    """Test utils/briefing.py."""

    @patch("utils.briefing.get_git_state")
    @patch("utils.briefing.get_commit_sha")
    def test_briefing_returns_all_sections(self, mock_sha, mock_git, app):
        """Briefing returns all 6 sections."""
        mock_git.return_value = {
            "available": True,
            "branch": "main",
            "dirty": False,
            "untracked": 0,
            "ahead": 0,
            "behind": 0,
        }
        mock_sha.return_value = "abc123"

        with app.app_context():
            from utils.briefing import generate_briefing

            result = generate_briefing("vms", "/fake/root")

        sections = result["sections"]
        assert "git_state" in sections
        assert "critical_findings" in sections
        assert "in_progress" in sections
        assert "upcoming_reviews" in sections
        assert "doc_freshness" in sections
        assert "export_status" in sections

    @patch("utils.briefing.get_git_state")
    @patch("utils.briefing.get_commit_sha")
    def test_briefing_captures_critical_findings(self, mock_sha, mock_git, app):
        """Briefing includes critical scan findings."""
        mock_git.return_value = {"available": False}
        mock_sha.return_value = None

        with app.app_context():
            # Create a scan result with critical findings
            scan = ScanResult(
                project="vms",
                scanner="coupling",
                severity="critical",
                finding_count=2,
                result_json=json.dumps(
                    {
                        "findings": [
                            {
                                "severity": "critical",
                                "file": "a.py",
                                "message": "broken ref",
                            },
                            {"severity": "info", "file": "b.py", "message": "ok"},
                        ]
                    }
                ),
            )
            _db.session.add(scan)
            _db.session.commit()

            from utils.briefing import generate_briefing

            result = generate_briefing("vms")

        findings = result["sections"]["critical_findings"]
        assert len(findings) == 1  # Only critical, not info
        assert findings[0]["severity"] == "critical"

    @patch("utils.briefing.get_git_state")
    @patch("utils.briefing.get_commit_sha")
    def test_briefing_captures_in_progress_items(self, mock_sha, mock_git, app):
        """Briefing includes in-progress work items."""
        mock_git.return_value = {"available": False}
        mock_sha.return_value = None

        with app.app_context():
            item = WorkItem(
                project="vms",
                title="fix bug",
                status="in_progress",
                category="bug",
                priority="high",
            )
            _db.session.add(item)
            _db.session.commit()

            from utils.briefing import generate_briefing

            result = generate_briefing("vms")

        in_progress = result["sections"]["in_progress"]
        assert len(in_progress) == 1
        assert in_progress[0]["title"] == "fix bug"


# ── Drift WorkItem Creation ──────────────────────────────


class TestDriftWorkItems:
    """Test auto-creation of drift work items."""

    def test_creates_drift_item(self, app):
        """Drift alert creates a work item."""
        from utils.receipt import create_drift_work_items

        with app.app_context():
            alerts = [
                {
                    "type": "drift",
                    "severity": "warning",
                    "message": "Code changed but no docs",
                    "action": "Export docs",
                },
            ]
            ids = create_drift_work_items("vms", alerts)
            assert len(ids) == 1

            item = WorkItem.query.get(ids[0])
            assert "DRIFT-" in item.source_id
            assert item.category == "review"

    def test_no_duplicate_drift_items(self, app):
        """Second drift call on same day doesn't create duplicates."""
        from utils.receipt import create_drift_work_items

        with app.app_context():
            alerts = [
                {
                    "type": "drift",
                    "severity": "warning",
                    "message": "Code changed",
                    "action": "Export docs",
                },
            ]
            ids1 = create_drift_work_items("vms", alerts)
            ids2 = create_drift_work_items("vms", alerts)
            assert len(ids1) == 1
            assert len(ids2) == 0  # Duplicate suppressed

    def test_skips_non_drift_alerts(self, app):
        """Non-drift alerts don't create work items."""
        from utils.receipt import create_drift_work_items

        with app.app_context():
            alerts = [
                {
                    "type": "coverage",
                    "severity": "info",
                    "message": "No tests",
                    "action": "Add tests",
                },
            ]
            ids = create_drift_work_items("vms", alerts)
            assert len(ids) == 0


# ── Session Routes ────────────────────────────────────────


class TestSessionRoutes:
    """Test web routes for session history."""

    def test_session_list_empty(self, client):
        """Sessions page renders with no sessions."""
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert b"No sessions yet" in resp.data

    def test_session_list_with_data(self, client, db):
        """Sessions page shows existing sessions."""
        session = SessionLog(
            project="vms",
            started_at=datetime(2026, 3, 18, 10, 0),
            ended_at=datetime(2026, 3, 18, 10, 30),
            files_changed=json.dumps(["a.py", "b.py"]),
        )
        db.session.add(session)
        db.session.commit()

        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert b"2026-03-18" in resp.data
        assert b"done" in resp.data

    def test_session_detail_with_receipt(self, client, db):
        """Session detail shows receipt data."""
        receipt_data = {
            "layers": {
                "1": {
                    "name": "Files Changed",
                    "count": 3,
                    "files": ["a.py", "b.py", "c.py"],
                },
                "2": {"name": "Routes", "count": 1, "files": ["routes/api.py"]},
            },
            "summary": "3 files (1 route)",
            "alerts": [],
        }
        session = SessionLog(
            project="vms",
            started_at=datetime(2026, 3, 18, 10, 0),
            receipt_json=json.dumps(receipt_data),
        )
        db.session.add(session)
        db.session.commit()

        resp = client.get(f"/sessions/{session.id}")
        assert resp.status_code == 200
        assert b"9-Layer Matrix" in resp.data
        assert b"3 files" in resp.data

    def test_session_detail_with_briefing(self, client, db):
        """Session detail shows briefing data."""
        briefing_data = {
            "sections": {
                "git_state": {
                    "available": True,
                    "branch": "feature-x",
                    "dirty": False,
                    "untracked": 0,
                    "ahead": 0,
                    "behind": 0,
                },
                "critical_findings": [],
                "in_progress": [],
                "upcoming_reviews": [],
                "doc_freshness": [],
                "export_status": [],
            }
        }
        session = SessionLog(
            project="vms",
            started_at=datetime(2026, 3, 18, 10, 0),
            briefing_json=json.dumps(briefing_data),
        )
        db.session.add(session)
        db.session.commit()

        resp = client.get(f"/sessions/{session.id}")
        assert resp.status_code == 200
        assert b"Briefing" in resp.data
        assert b"feature-x" in resp.data

    def test_session_detail_404(self, client):
        """Session detail returns 404 for nonexistent session."""
        resp = client.get("/sessions/9999")
        assert resp.status_code == 404

    def test_session_active_badge(self, client, db):
        """Active sessions (no ended_at) show active badge."""
        session = SessionLog(
            project="vms",
            started_at=datetime(2026, 3, 18, 10, 0),
        )
        db.session.add(session)
        db.session.commit()

        resp = client.get("/sessions")
        assert b"active" in resp.data


# ── Dashboard Sessions Panel ─────────────────────────────


class TestDashboardSessionsPanel:
    """Test the Sessions panel on the dashboard."""

    def test_dashboard_sessions_panel_empty(self, client, db):
        """Dashboard shows empty sessions panel."""
        from models import WorkItem

        db.session.add(WorkItem(project="vms", title="seed", status="backlog"))
        db.session.commit()
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Sessions" in resp.data
        assert b"No sessions yet" in resp.data

    def test_dashboard_sessions_panel_with_session(self, client, db):
        """Dashboard shows session data when sessions exist."""
        from models import WorkItem

        db.session.add(WorkItem(project="vms", title="seed", status="backlog"))
        session = SessionLog(
            project="vms",
            started_at=datetime(2026, 3, 18, 10, 0),
        )
        db.session.add(session)
        db.session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Last Session" in resp.data

    def test_dashboard_sessions_panel_links_to_sessions(self, client):
        """Dashboard sessions panel links to /sessions."""
        resp = client.get("/")
        assert b"/sessions" in resp.data

    def test_nav_has_sessions_link(self, client):
        """Navigation bar includes Sessions link."""
        resp = client.get("/")
        assert b"Sessions" in resp.data

    def test_footer_phase_4b(self, client):
        """Footer shows Phase 4b."""
        resp = client.get("/")
        assert b"Phase 4c" in resp.data
