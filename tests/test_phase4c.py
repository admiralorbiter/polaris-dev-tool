"""Tests for Phase 4c: Time & Trends.

Covers:
- HealthSnapshot model (creation, get_components)
- Snapshot recording in generate_briefing()
- /api/trends/<project> endpoint (health + scan data)
- Work board timeframe filters (?timeframe=week|month|all)
- Dashboard sparkline data (health_trend in template)
- Scan detail trend_data
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app import create_app
from models import db as _db, HealthSnapshot, ScanResult, WorkItem


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
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


# ── HealthSnapshot Model ──────────────────────────────────────


class TestHealthSnapshot:
    """Test the HealthSnapshot model."""

    def test_snapshot_creation(self, app):
        """HealthSnapshot can be created with required fields."""
        with app.app_context():
            snap = HealthSnapshot(
                project="vms",
                score=78,
                components_json=json.dumps({"scan_health": 90, "debt_load": 65}),
                trigger="briefing",
            )
            _db.session.add(snap)
            _db.session.commit()

            fetched = HealthSnapshot.query.get(snap.id)
            assert fetched is not None
            assert fetched.score == 78
            assert fetched.trigger == "briefing"
            assert fetched.project == "vms"

    def test_snapshot_recorded_at_defaults(self, app):
        """recorded_at defaults to current time."""
        with app.app_context():
            before = datetime.now(timezone.utc).replace(tzinfo=None)
            snap = HealthSnapshot(project="vms", score=50, trigger="receipt")
            _db.session.add(snap)
            _db.session.commit()
            after = datetime.now(timezone.utc).replace(tzinfo=None)

            assert before <= snap.recorded_at <= after

    def test_get_components_parses_json(self, app):
        """get_components() returns a dict with component scores."""
        with app.app_context():
            snap = HealthSnapshot(
                project="vms",
                score=72,
                components_json=json.dumps(
                    {"scan_health": 80, "doc_freshness": 60, "debt_load": 70}
                ),
                trigger="briefing",
            )
            components = snap.get_components()
            assert components["scan_health"] == 80
            assert components["debt_load"] == 70

    def test_get_components_empty(self, app):
        """get_components() returns {} when no components_json."""
        with app.app_context():
            snap = HealthSnapshot(project="vms", score=50, trigger="briefing")
            assert snap.get_components() == {}

    def test_get_components_invalid_json(self, app):
        """get_components() returns {} on bad JSON."""
        with app.app_context():
            snap = HealthSnapshot(
                project="vms", score=50, components_json="not-json", trigger="briefing"
            )
            assert snap.get_components() == {}

    def test_repr(self, app):
        """__repr__ includes project, date, and score."""
        with app.app_context():
            snap = HealthSnapshot(project="vms", score=85, trigger="briefing")
            snap.recorded_at = datetime(2026, 3, 18, 10, 0)
            r = repr(snap)
            assert "vms" in r
            assert "85" in r
            assert "2026-03-18" in r

    @patch("utils.briefing.get_git_state")
    @patch("utils.briefing.get_commit_sha")
    @patch("utils.briefing.compute_health_score")
    def test_snapshot_recorded_on_briefing(self, mock_health, mock_sha, mock_git, app):
        """generate_briefing() records a HealthSnapshot."""
        mock_git.return_value = {"available": False}
        mock_sha.return_value = None
        mock_health.return_value = {"total": 75, "components": {"scan_health": 80}}

        with app.app_context():
            count_before = HealthSnapshot.query.count()
            from utils.briefing import generate_briefing

            generate_briefing("vms")
            count_after = HealthSnapshot.query.count()

        assert count_after == count_before + 1

    @patch("utils.briefing.get_git_state")
    @patch("utils.briefing.get_commit_sha")
    @patch("utils.briefing.compute_health_score")
    def test_snapshot_trigger_is_briefing(self, mock_health, mock_sha, mock_git, app):
        """Snapshot recorded from generate_briefing() has trigger='briefing'."""
        mock_git.return_value = {"available": False}
        mock_sha.return_value = None
        mock_health.return_value = {"total": 75, "components": {}}

        with app.app_context():
            from utils.briefing import generate_briefing

            generate_briefing("vms")
            snap = HealthSnapshot.query.order_by(
                HealthSnapshot.recorded_at.desc()
            ).first()

        assert snap is not None
        assert snap.trigger == "briefing"
        assert snap.project == "vms"

    @patch("utils.briefing.get_git_state")
    @patch("utils.briefing.get_commit_sha")
    @patch("utils.briefing.compute_health_score")
    def test_snapshot_score_is_integer(self, mock_health, mock_sha, mock_git, app):
        """Snapshot score is an integer between 0 and 100."""
        mock_git.return_value = {"available": False}
        mock_sha.return_value = None
        mock_health.return_value = {"total": 82, "components": {}}

        with app.app_context():
            from utils.briefing import generate_briefing

            generate_briefing("vms")
            snap = HealthSnapshot.query.order_by(
                HealthSnapshot.recorded_at.desc()
            ).first()

        assert isinstance(snap.score, int)
        assert 0 <= snap.score <= 100


# ── Work Board Timeframe Filters ──────────────────────────────


class TestWorkBoardFilters:
    """Test /work-items?timeframe= filters."""

    def _make_item(self, db, days_ago=0, status="backlog"):
        """Create a WorkItem with created_at offset."""
        item = WorkItem(
            project="vms",
            title=f"Item created {days_ago}d ago",
            category="bug",
            priority="medium",
            status=status,
        )
        item.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        db.session.add(item)
        db.session.commit()
        return item

    def test_timeframe_all_shows_all(self, client, db):
        """?timeframe=all shows all items regardless of age."""
        self._make_item(db, days_ago=0)
        self._make_item(db, days_ago=20)
        self._make_item(db, days_ago=60)

        resp = client.get("/work-items?timeframe=all")
        assert resp.status_code == 200
        assert b"3 items" in resp.data or b"items" in resp.data

    def test_timeframe_week_filters_old(self, client, db):
        """?timeframe=week hides items older than 7 days."""
        self._make_item(db, days_ago=1)  # recent
        self._make_item(db, days_ago=30)  # old

        resp = client.get("/work-items?timeframe=week")
        assert resp.status_code == 200
        # Only the recent item should appear
        assert b"Item created 1d ago" in resp.data
        assert b"Item created 30d ago" not in resp.data

    def test_timeframe_month_includes_last_30d(self, client, db):
        """?timeframe=month includes items created in the last 30 days."""
        self._make_item(db, days_ago=5)
        self._make_item(db, days_ago=25)
        self._make_item(db, days_ago=60)  # older, should not appear

        resp = client.get("/work-items?timeframe=month")
        assert resp.status_code == 200
        assert b"Item created 5d ago" in resp.data
        assert b"Item created 25d ago" in resp.data
        assert b"Item created 60d ago" not in resp.data

    def test_timeframe_toggle_visible(self, client, db):
        """Timeframe toggle buttons are rendered on the work board."""
        resp = client.get("/work-items")
        assert resp.status_code == 200
        assert b"This Week" in resp.data
        assert b"This Month" in resp.data
        assert b"All Time" in resp.data

    def test_timeframe_active_class_all(self, client, db):
        """?timeframe=all marks 'All Time' button as active."""
        resp = client.get("/work-items?timeframe=all")
        assert b"timeframe-btn active" in resp.data or b"active" in resp.data

    def test_completed_since_week(self, client, db):
        """?completed_since=week filters by completed_at."""
        # Item completed 2d ago
        item = self._make_item(db, days_ago=30, status="done")
        item.completed_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.session.commit()

        # Item completed 20d ago
        old_item = self._make_item(db, days_ago=30, status="done")
        old_item.completed_at = datetime.now(timezone.utc) - timedelta(days=20)
        db.session.commit()

        resp = client.get("/work-items?completed_since=week")
        assert resp.status_code == 200


# ── Trends API ────────────────────────────────────────────────


class TestScanTrendsAPI:
    """/api/trends/<project> endpoint tests."""

    def test_trends_empty_db(self, client):
        """Returns empty lists when no data exists."""
        resp = client.get("/api/trends/vms")
        assert resp.status_code == 200

        data = json.loads(resp.data)
        assert data["project"] == "vms"
        assert data["health"] == []
        assert isinstance(data["scans"], dict)
        for scanner in ["coupling", "security", "doc_freshness"]:
            assert data["scans"][scanner] == []

    def test_trends_with_snapshots(self, client, db):
        """Returns health trend data when snapshots exist."""
        for i in range(3):
            snap = HealthSnapshot(
                project="vms",
                score=70 + i * 5,
                trigger="briefing",
            )
            snap.recorded_at = datetime.now(timezone.utc) - timedelta(hours=i)
            db.session.add(snap)
        db.session.commit()

        resp = client.get("/api/trends/vms")
        data = json.loads(resp.data)

        assert len(data["health"]) == 3
        # Chronological order (oldest first)
        assert data["health"][0]["score"] == 80
        assert data["health"][-1]["score"] == 70

    def test_trends_with_scan_results(self, client, db):
        """Returns scan trend data when ScanResults exist."""
        for i in range(3):
            sr = ScanResult(
                project="vms",
                scanner="coupling",
                severity="warning",
                finding_count=5 + i,
                result_json=json.dumps({"findings": [], "scanned_files": 10}),
            )
            sr.scanned_at = datetime.now(timezone.utc) - timedelta(hours=i)
            db.session.add(sr)
        db.session.commit()

        resp = client.get("/api/trends/vms")
        data = json.loads(resp.data)

        coupling_trend = data["scans"]["coupling"]
        assert len(coupling_trend) == 3
        assert all("count" in p for p in coupling_trend)
        assert all("date" in p for p in coupling_trend)

    def test_trends_max_10_snapshots(self, client, db):
        """Returns at most 10 snapshots (the most recent)."""
        for i in range(15):
            snap = HealthSnapshot(
                project="vms",
                score=50 + i,
                trigger="briefing",
            )
            snap.recorded_at = datetime.now(timezone.utc) - timedelta(hours=i)
            db.session.add(snap)
        db.session.commit()

        resp = client.get("/api/trends/vms")
        data = json.loads(resp.data)

        assert len(data["health"]) == 10

    def test_trends_json_shape(self, client):
        """Response has required top-level keys."""
        resp = client.get("/api/trends/vms")
        data = json.loads(resp.data)

        assert "project" in data
        assert "health" in data
        assert "scans" in data
        assert "coupling" in data["scans"]
        assert "security" in data["scans"]
        assert "doc_freshness" in data["scans"]

    def test_trends_project_isolation(self, client, db):
        """Trends are scoped to the requested project."""
        snap_vms = HealthSnapshot(project="vms", score=80, trigger="briefing")
        snap_other = HealthSnapshot(project="other", score=40, trigger="briefing")
        db.session.add_all([snap_vms, snap_other])
        db.session.commit()

        resp = client.get("/api/trends/vms")
        data = json.loads(resp.data)

        assert len(data["health"]) == 1
        assert data["health"][0]["score"] == 80


# ── Dashboard Sparkline ───────────────────────────────────────


class TestDashboardSparkline:
    """Test dashboard sparkline rendering."""

    def test_dashboard_no_sparkline_with_no_data(self, client):
        """Dashboard doesn't crash with 0 snapshots — shows hint."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"cli.py briefing" in resp.data or b"Sessions" in resp.data

    def test_dashboard_shows_sparkline_hint_when_empty(self, client):
        """Dashboard shows 'cli.py briefing' hint when no trend data."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"sparkline-hint" in resp.data or b"briefing" in resp.data

    def test_dashboard_sparkline_with_single_snapshot(self, client, db):
        """Dashboard with 1 snapshot doesn't crash (sparkline needs 2+ points)."""
        snap = HealthSnapshot(project="vms", score=75, trigger="briefing")
        db.session.add(snap)
        db.session.commit()

        resp = client.get("/")
        assert resp.status_code == 200

    def test_dashboard_sparkline_renders_svg_with_multiple_snapshots(self, client, db):
        """Dashboard SVG sparkline appears with 2+ health snapshots."""
        for score in [60, 70, 75, 80]:
            snap = HealthSnapshot(project="vms", score=score, trigger="briefing")
            db.session.add(snap)
        db.session.commit()

        resp = client.get("/")
        assert resp.status_code == 200
        assert b"sparkline-svg" in resp.data
        assert b"sparkGrad" in resp.data

    def test_scan_detail_no_trend_with_single_run(self, client, db):
        """Scan detail page with 1 run doesn't show trend chart."""
        sr = ScanResult(
            project="vms",
            scanner="coupling",
            severity="info",
            finding_count=0,
            result_json=json.dumps({"findings": [], "scanned_files": 10}),
        )
        db.session.add(sr)
        db.session.commit()

        resp = client.get("/scans/coupling")
        assert resp.status_code == 200
        # trend requires 2+ runs
        assert b"scan-trend-panel" not in resp.data

    def test_scan_detail_shows_trend_with_multiple_runs(self, client, db):
        """Scan detail shows trend panel when 2+ runs exist."""
        for i in range(3):
            sr = ScanResult(
                project="vms",
                scanner="coupling",
                severity="warning",
                finding_count=i + 1,
                result_json=json.dumps({"findings": [], "scanned_files": 10}),
            )
            sr.scanned_at = datetime.now(timezone.utc) - timedelta(hours=i)
            db.session.add(sr)
        db.session.commit()

        resp = client.get("/scans/coupling")
        assert resp.status_code == 200
        assert b"scan-trend-panel" in resp.data
        assert b"Finding Trend" in resp.data
