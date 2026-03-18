"""Tests for API routes."""


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

    def test_dashboard_shows_stats(self, client):
        """Dashboard shows stat panels."""
        response = client.get("/")
        assert b"Work Items" in response.data
        assert b"Features" in response.data
        assert b"Health Score" in response.data
