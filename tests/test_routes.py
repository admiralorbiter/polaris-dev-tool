"""Tests for API routes."""

from models import WorkItem


class TestHealthEndpoint:
    """Tests for GET /api/health."""

    def test_health_returns_ok(self, client):
        """Health check returns 200 with status ok."""
        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert "version" in data

    def test_health_returns_json(self, client):
        """Health check returns JSON content type."""
        response = client.get("/api/health")
        assert response.content_type == "application/json"


class TestDashboard:
    """Tests for the dashboard route."""

    def test_dashboard_loads(self, client):
        """Dashboard returns 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_dashboard_contains_title(self, client):
        """Dashboard HTML contains the page title."""
        response = client.get("/")
        assert b"Polaris DevTools" in response.data

    def test_dashboard_shows_stats(self, client, db):
        """Dashboard shows stat panels (requires data to skip wizard)."""
        db.session.add(WorkItem(project="vms", title="seed", status="backlog"))
        db.session.commit()
        response = client.get("/")
        assert b"Work Items" in response.data
        assert b"Features" in response.data
        assert b"Health Score" in response.data

    def test_dashboard_shows_wizard_when_empty(self, client):
        """Empty DB shows setup wizard instead of normal dashboard."""
        response = client.get("/")
        assert b"Welcome to Polaris DevTools" in response.data
        assert b"setup-wizard" in response.data
