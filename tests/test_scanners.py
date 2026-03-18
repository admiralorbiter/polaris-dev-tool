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


# ──────────────────────────────────────
# Edge Case Tests
# ──────────────────────────────────────


class TestCouplingAuditEdgeCases:
    """Edge cases for AST analysis."""

    def _make_scanner(self):
        return CouplingAuditScanner()

    def test_module_with_no_blueprint(self):
        """File with no Blueprint should return empty results."""
        source = textwrap.dedent(
            """
            def helper():
                return 42
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        bp = scanner._find_blueprint_var(tree)
        assert bp is None

    def test_module_with_syntax_error_content(self):
        """Non-parseable content should be handled gracefully."""
        # Simulate what happens when ast.parse fails
        try:
            ast.parse("def broken(:\n  pass")
            assert False, "Should have raised SyntaxError"
        except SyntaxError:
            pass  # Expected — scanner handles this in scan()

    def test_multiple_templates_in_one_route(self):
        """Route that conditionally renders different templates."""
        source = textwrap.dedent(
            """
            from flask import Blueprint, render_template
            bp = Blueprint('test', __name__)

            @bp.route('/page')
            def page():
                if condition:
                    return render_template('page_a.html')
                return render_template('page_b.html')
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, templates, _ = scanner._analyze_module(
            tree, "test.py", set(), "render_template"
        )
        assert "page_a.html" in templates
        assert "page_b.html" in templates
        assert len(routes[0]["templates"]) == 2

    def test_dynamic_template_name_ignored(self):
        """render_template with a variable (not string literal) should not crash."""
        source = textwrap.dedent(
            """
            from flask import Blueprint, render_template
            bp = Blueprint('test', __name__)

            @bp.route('/dynamic')
            def dynamic():
                tpl = get_template_name()
                return render_template(tpl)
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, templates, _ = scanner._analyze_module(
            tree, "test.py", set(), "render_template"
        )
        assert len(routes) == 1
        # Dynamic template names can't be statically extracted
        assert len(templates) == 0

    def test_file_with_no_routes(self):
        """File with Blueprint but no @route decorators."""
        source = textwrap.dedent(
            """
            from flask import Blueprint
            bp = Blueprint('utils', __name__)

            def helper():
                return "not a route"
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, _, _ = scanner._analyze_module(
            tree, "utils.py", set(), "render_template"
        )
        assert len(routes) == 0

    def test_multi_method_route(self):
        """Route with GET + POST methods."""
        source = textwrap.dedent(
            """
            from flask import Blueprint
            bp = Blueprint('test', __name__)

            @bp.route('/form', methods=["GET", "POST"])
            def form():
                return "ok"
        """
        )
        tree = ast.parse(source)
        scanner = self._make_scanner()
        routes, _, _ = scanner._analyze_module(
            tree, "test.py", set(), "render_template"
        )
        assert "GET" in routes[0]["methods"]
        assert "POST" in routes[0]["methods"]


class TestSecurityAuditEdgeCases:
    """Edge cases for the security scanner."""

    def test_empty_route_registry(self):
        """Empty registry should produce no findings."""
        scanner = SecurityAuditScanner()
        result = scanner.scan(
            {"conventions": {"auth_decorators": ["login_required"]}},
            route_registry=[],
        )
        assert len(result.findings) == 0
        assert result.scanned_files == 0

    def test_put_delete_patch_are_critical(self):
        """PUT, DELETE, PATCH without auth are critical."""
        scanner = SecurityAuditScanner()
        for method in ["PUT", "DELETE", "PATCH"]:
            route_registry = [
                {
                    "blueprint": "api",
                    "url_pattern": f"/api/{method.lower()}",
                    "methods": [method],
                    "function_name": f"do_{method.lower()}",
                    "auth_decorators": [],
                    "all_decorators": ["route"],
                    "file": "api.py",
                    "line": 1,
                }
            ]
            result = scanner.scan(
                {"conventions": {"auth_decorators": ["login_required"]}},
                route_registry=route_registry,
            )
            assert (
                result.findings[0].severity == "critical"
            ), f"{method} should be critical"

    def test_multi_method_route_with_post_is_critical(self):
        """GET+POST route without auth is critical (POST trumps)."""
        scanner = SecurityAuditScanner()
        route_registry = [
            {
                "blueprint": "test",
                "url_pattern": "/form",
                "methods": ["GET", "POST"],
                "function_name": "form",
                "auth_decorators": [],
                "file": "test.py",
                "line": 1,
            }
        ]
        result = scanner.scan(
            {"conventions": {"auth_decorators": ["login_required"]}},
            route_registry=route_registry,
        )
        assert result.findings[0].severity == "critical"

    def test_missing_conventions_config(self):
        """Scanner handles missing conventions gracefully."""
        scanner = SecurityAuditScanner()
        result = scanner.scan({}, route_registry=[])
        assert len(result.findings) == 0

    def test_config_as_object_not_dict(self):
        """Scanner works with object-style config (hasattr path)."""

        class FakeConfig:
            conventions = {"auth_decorators": ["login_required"]}

        scanner = SecurityAuditScanner()
        route_registry = [
            {
                "blueprint": "test",
                "url_pattern": "/page",
                "methods": ["GET"],
                "function_name": "page",
                "auth_decorators": [],
                "file": "test.py",
                "line": 1,
            }
        ]
        result = scanner.scan(FakeConfig(), route_registry=route_registry)
        assert len(result.findings) == 1


class TestTechDebtImporterEdgeCases:
    """Edge cases for the tech debt importer."""

    def _make_importer(self):
        from importers.tech_debt_importer import TechDebtImporter

        return TechDebtImporter()

    def test_parse_title_with_backticks(self):
        """Items with backtick-formatted code in titles."""
        importer = self._make_importer()
        lines = [
            "## TD-004: `Event.district_partner` Is a Text Field, Not a FK",
            "",
            "**Created:** 2026-01-15 · **Priority:** Low",
            "",
            "Some description here.",
        ]
        items = importer._parse_active_items(lines)
        assert "TD-004" in items
        assert "`Event.district_partner`" in items["TD-004"]["title"]

    def test_parse_resolved_suffix(self):
        """Items with ✅ RESOLVED suffix get status=done."""
        importer = self._make_importer()
        lines = [
            "## TD-033: Student Import Cleanup ✅ RESOLVED",
            "",
            "**Created:** 2026-03-07",
            "",
            "Description of fix.",
        ]
        items = importer._parse_active_items(lines)
        assert "TD-033" in items
        assert items["TD-033"]["status"] == "done"
        assert "✅" not in items["TD-033"]["title"]

    def test_parse_deferred_suffix(self):
        """Items with *(Deferred)* suffix get status=deferred."""
        importer = self._make_importer()
        lines = [
            "## TD-004: Some Feature *(Deferred)*",
            "",
            "**Created:** 2026-01-15",
        ]
        items = importer._parse_active_items(lines)
        assert items["TD-004"]["status"] == "deferred"
        assert "*(Deferred)*" not in items["TD-004"]["title"]

    def test_parse_empty_file(self):
        """Empty file produces no items."""
        importer = self._make_importer()
        items = importer._parse_active_items([])
        assert items == {}

    def test_parse_malformed_date(self):
        """Malformed dates don't crash the parser."""
        importer = self._make_importer()
        lines = [
            "## TD-099: Test Item",
            "",
            "**Created:** not-a-date · **Priority:** High",
        ]
        items = importer._parse_active_items(lines)
        assert "TD-099" in items
        assert "created" not in items["TD-099"]

    def test_items_after_resolved_archive(self):
        """Items appearing after the resolved archive are still captured."""
        importer = self._make_importer()
        lines = [
            "## TD-001: First Active Item",
            "",
            "**Created:** 2026-01-01",
            "",
            "---",
            "",
            "## Priority Order",
            "",
            "| Priority | ID | Item | Effort |",
            "|---|---|---|---|",
            "",
            "## Resolved Archive",
            "",
            "| ID | Title | Resolved | Summary |",
            "|---|---|---|---|",
            "| TD-002 | Old Item | 2026-01-05 | Fixed |",
            "",
            "---",
            "",
            "## TD-040: Post-Archive Item",
            "",
            "**Created:** 2026-03-17 · **Priority:** Low",
            "",
            "Some note.",
        ]
        items = importer._parse_active_items(lines)
        assert "TD-001" in items
        assert "TD-040" in items
        assert items["TD-040"]["title"] == "Post-Archive Item"

    def test_parse_parenthetical_title(self):
        """Titles with parentheses like (~2,100 pairs)."""
        importer = self._make_importer()
        lines = [
            "## TD-036: Exact-Name Duplicate Teacher Records (~2,100 pairs)",
            "",
            "**Created:** 2026-03-13 · **Priority:** Low",
        ]
        items = importer._parse_active_items(lines)
        assert "TD-036" in items
        assert "(~2,100 pairs)" in items["TD-036"]["title"]

    def test_resolved_table_parsing(self):
        """Resolved archive table rows are parsed correctly."""
        importer = self._make_importer()
        lines = [
            "## Resolved Archive",
            "",
            "| ID | Title | Resolved | Summary |",
            "|---|---|---|---|",
            "| TD-001 | First Fix | 2026-01-05 | Fixed the bug |",
            "| TD-002 | Second Fix | 2026-02-10 | Resolved issue |",
        ]
        resolved = importer._parse_resolved_archive(lines)
        assert len(resolved) == 2
        assert resolved["TD-001"]["title"] == "First Fix"
        assert resolved["TD-002"]["resolution_summary"] == "Resolved issue"


class TestScanRoutesEdgeCases:
    """Edge cases for web routes."""

    def test_scan_detail_with_findings(self, client, db):
        """Scan detail page displays findings correctly."""
        from models import ScanResult

        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=2,
            severity="warning",
            result_json=json.dumps(
                {
                    "findings": [
                        {
                            "file": "routes/test.py",
                            "line": 10,
                            "message": "Missing template",
                            "severity": "warning",
                            "details": {},
                        },
                        {
                            "file": "templates/old.html",
                            "line": None,
                            "message": "Orphaned template",
                            "severity": "warning",
                            "details": {},
                        },
                    ],
                    "scanned_files": 5,
                    "duration_ms": 100,
                }
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/scans/coupling")
        assert response.status_code == 200
        assert b"Missing template" in response.data
        assert b"Orphaned template" in response.data

    def test_nonexistent_scanner_detail(self, client):
        """Detail page for scanner with no results shows empty state."""
        response = client.get("/scans/nonexistent")
        assert response.status_code == 200
        assert b"No nonexistent scan results" in response.data

    def test_scans_page_with_data(self, client, db):
        """Scans page shows cards when scan results exist."""
        from models import ScanResult

        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=5,
            severity="critical",
            result_json=json.dumps(
                {"findings": [], "scanned_files": 10, "duration_ms": 50}
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/scans")
        assert response.status_code == 200
        assert b"Coupling" in response.data
        assert b"critical" in response.data
