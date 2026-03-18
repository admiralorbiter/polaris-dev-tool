"""Tests for scanners."""

import ast
import json
import textwrap

from scanners.coupling_audit import CouplingAuditScanner
from scanners.security_audit import SecurityAuditScanner


class TestCouplingAuditAST:
    """Tests for the coupling scanner's AST analysis."""

    def _make_scanner(self):
        return CouplingAuditScanner()

    def test_extract_route_from_simple_decorator(self):
        """Parse a simple @bp.route('/path') decorator."""
        source = textwrap.dedent(
            """
            from flask import Blueprint
            bp = Blueprint('test', __name__)

            @bp.route('/hello')
            def hello():
                return "hi"
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, templates, url_fors = scanner._analyze_module(
            tree, "test.py", {"login_required"}, "render_template"
        )
        assert len(routes) == 1
        assert routes[0]["url_pattern"] == "/hello"
        assert routes[0]["function_name"] == "hello"
        assert routes[0]["methods"] == ["GET"]

    def test_extract_post_route(self):
        """Parse a route with methods=["POST"]."""
        source = textwrap.dedent(
            """
            from flask import Blueprint
            bp = Blueprint('test', __name__)

            @bp.route('/submit', methods=["POST"])
            def submit():
                return "ok"
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, _, _ = scanner._analyze_module(
            tree, "test.py", set(), "render_template"
        )
        assert routes[0]["methods"] == ["POST"]

    def test_extract_template_reference(self):
        """Find render_template calls."""
        source = textwrap.dedent(
            """
            from flask import Blueprint, render_template
            bp = Blueprint('test', __name__)

            @bp.route('/')
            def index():
                return render_template('dashboard.html', data=None)
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, templates, _ = scanner._analyze_module(
            tree, "test.py", set(), "render_template"
        )
        assert "dashboard.html" in templates
        assert routes[0]["templates"] == ["dashboard.html"]

    def test_extract_auth_decorators(self):
        """Detect auth decorators on routes."""
        source = textwrap.dedent(
            """
            from flask import Blueprint
            bp = Blueprint('test', __name__)

            @bp.route('/admin')
            @login_required
            @admin_required
            def admin_page():
                return "secret"
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, _, _ = scanner._analyze_module(
            tree, "test.py", {"login_required", "admin_required"}, "render_template"
        )
        assert "login_required" in routes[0]["auth_decorators"]
        assert "admin_required" in routes[0]["auth_decorators"]

    def test_extract_url_for_targets(self):
        """Find url_for calls in module."""
        source = textwrap.dedent(
            """
            from flask import Blueprint, url_for
            bp = Blueprint('test', __name__)

            @bp.route('/')
            def index():
                return url_for('test.other')
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        _, _, url_fors = scanner._analyze_module(
            tree, "test.py", set(), "render_template"
        )
        assert "test.other" in url_fors

    def test_blueprint_detection(self):
        """Detect blueprint variable name."""
        source = textwrap.dedent(
            """
            from flask import Blueprint
            district_bp = Blueprint('district', __name__)
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        bp_name = scanner._find_blueprint_var(tree)
        assert bp_name == "district_bp"


class TestSecurityAudit:
    """Tests for the security scanner."""

    def test_flags_unprotected_route(self):
        """Unprotected GET route gets a warning."""
        scanner = SecurityAuditScanner()
        route_registry = [
            {
                "blueprint": "test",
                "url_pattern": "/public",
                "methods": ["GET"],
                "function_name": "public_page",
                "auth_decorators": [],
                "all_decorators": ["route"],
                "templates": [],
                "file": "test.py",
                "line": 10,
            }
        ]
        result = scanner.scan(
            {"conventions": {"auth_decorators": ["login_required"]}},
            route_registry=route_registry,
        )
        assert len(result.findings) == 1
        assert result.findings[0].severity == "warning"

    def test_flags_unprotected_post_as_critical(self):
        """Unprotected POST route gets critical severity."""
        scanner = SecurityAuditScanner()
        route_registry = [
            {
                "blueprint": "test",
                "url_pattern": "/submit",
                "methods": ["POST"],
                "function_name": "submit",
                "auth_decorators": [],
                "all_decorators": ["route"],
                "file": "test.py",
                "line": 10,
            }
        ]
        result = scanner.scan(
            {"conventions": {"auth_decorators": ["login_required"]}},
            route_registry=route_registry,
        )
        assert len(result.findings) == 1
        assert result.findings[0].severity == "critical"

    def test_ignores_protected_routes(self):
        """Protected routes don't generate findings."""
        scanner = SecurityAuditScanner()
        route_registry = [
            {
                "blueprint": "test",
                "url_pattern": "/admin",
                "methods": ["GET"],
                "function_name": "admin",
                "auth_decorators": ["login_required"],
                "all_decorators": ["route", "login_required"],
                "file": "test.py",
                "line": 10,
            }
        ]
        result = scanner.scan(
            {"conventions": {"auth_decorators": ["login_required"]}},
            route_registry=route_registry,
        )
        assert len(result.findings) == 0

    def test_respects_public_allowlist(self):
        """Routes in the intentionally_public list are skipped."""
        scanner = SecurityAuditScanner()
        route_registry = [
            {
                "blueprint": "api",
                "url_pattern": "/api/health",
                "methods": ["GET"],
                "function_name": "health",
                "auth_decorators": [],
                "all_decorators": ["route"],
                "file": "api.py",
                "line": 5,
            }
        ]
        result = scanner.scan(
            {
                "conventions": {
                    "auth_decorators": ["login_required"],
                    "intentionally_public_routes": ["api.health"],
                }
            },
            route_registry=route_registry,
        )
        assert len(result.findings) == 0


class TestScanRoutes:
    """Tests for the scan result web routes."""

    def test_scans_page_loads(self, client):
        """Scans page returns 200."""
        response = client.get("/scans")
        assert response.status_code == 200
        assert b"Scan Results" in response.data

    def test_scan_detail_empty(self, client):
        """Scan detail page returns 200 even with no results."""
        response = client.get("/scans/coupling")
        assert response.status_code == 200

    def test_routes_page_loads(self, client):
        """Routes page returns 200."""
        response = client.get("/routes")
        assert response.status_code == 200
        assert b"Route Registry" in response.data

    def test_routes_page_with_data(self, client, db):
        """Routes page shows route data when scan exists."""
        from models import ScanResult

        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=0,
            result_json=json.dumps(
                {
                    "route_registry": [
                        {
                            "blueprint": "test",
                            "url_pattern": "/test",
                            "methods": ["GET"],
                            "function_name": "test_view",
                            "auth_decorators": ["login_required"],
                            "templates": ["test.html"],
                            "file": "routes/test.py",
                            "line": 10,
                        }
                    ]
                }
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/routes")
        assert response.status_code == 200
        assert b"/test" in response.data
        assert b"test_view" in response.data
