"""Tests for the AI context formatter."""

import os
import tempfile

from utils.context_formatter import (
    format_finding_context,
    format_all_findings,
    _extract_snippet,
)


class TestFormatFindingContext:
    """Tests for single finding formatting."""

    def test_basic_finding_format(self):
        """Basic finding produces problem, location, and context sections."""
        finding = {
            "file": "routes/auth/api.py",
            "line": 102,
            "message": "Unprotected route: /token (POST)",
            "severity": "critical",
            "details": {
                "blueprint": "auth",
                "function_name": "create_token",
                "url_pattern": "/token",
                "methods": ["POST"],
            },
        }
        result = format_finding_context(finding, "security")
        assert "CRITICAL" in result
        assert "Unprotected route" in result
        assert "`routes/auth/api.py`" in result
        assert "line 102" in result
        assert "`auth`" in result
        assert "`create_token()`" in result
        assert "Suggested Fix" in result

    def test_coupling_warning_format(self):
        """Coupling warning includes orphaned template guidance."""
        finding = {
            "file": "templates/old.html",
            "line": None,
            "message": "Orphaned template: 'old.html'",
            "severity": "warning",
            "details": {},
        }
        result = format_finding_context(finding, "coupling")
        assert "WARNING" in result
        assert "Orphaned template" in result
        assert "{% extends %}" in result

    def test_unknown_scanner_still_works(self):
        """Unknown scanner name produces output without context/fix sections."""
        finding = {
            "file": "test.py",
            "line": 1,
            "message": "Some issue",
            "severity": "info",
            "details": {},
        }
        result = format_finding_context(finding, "unknown_scanner")
        assert "INFO" in result
        assert "Some issue" in result

    def test_finding_without_details(self):
        """Finding with empty details doesn't crash."""
        finding = {
            "file": "test.py",
            "line": None,
            "message": "Generic issue",
            "severity": "warning",
        }
        result = format_finding_context(finding, "coupling")
        assert "WARNING" in result
        assert "Generic issue" in result

    def test_finding_with_null_details(self):
        """Finding with details explicitly None doesn't crash.

        This happens when scan JSON has "details": null — dict.get()
        returns None (not the default {}) because the key exists.
        """
        finding = {
            "file": "test.py",
            "line": 5,
            "message": "Some issue",
            "severity": "critical",
            "details": None,
        }
        result = format_finding_context(finding, "security")
        assert "CRITICAL" in result
        assert "Some issue" in result

    def test_code_snippet_included(self):
        """When project_root is provided, code snippet is included."""
        # Create a temp file with known content
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
        ) as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")
            f.write("target line\nline 7\nline 8\nline 9\nline 10\n")
            temp_path = f.name

        try:
            # The file path relative to "project_root"
            rel_path = os.path.basename(temp_path)
            finding = {
                "file": rel_path,
                "line": 6,
                "message": "Issue here",
                "severity": "warning",
                "details": {},
            }
            result = format_finding_context(
                finding, "coupling", project_root=tempfile.gettempdir()
            )
            assert "Relevant Code" in result
            assert "target line" in result
        finally:
            os.unlink(temp_path)


class TestFormatAllFindings:
    """Tests for batch finding formatting."""

    def test_formats_multiple_findings(self):
        """Multiple findings are numbered and separated."""
        findings = [
            {
                "file": "a.py",
                "line": 1,
                "message": "Issue A",
                "severity": "critical",
                "details": {},
            },
            {
                "file": "b.py",
                "line": 2,
                "message": "Issue B",
                "severity": "warning",
                "details": {},
            },
        ]
        result = format_all_findings(findings, "security")
        assert "Finding 1/2" in result
        assert "Finding 2/2" in result
        assert "Issue A" in result
        assert "Issue B" in result
        assert "2 findings" in result

    def test_includes_errors_section(self):
        """Scanner errors appear in a dedicated section."""
        findings = [
            {
                "file": "a.py",
                "line": 1,
                "message": "Issue",
                "severity": "warning",
                "details": {},
            },
        ]
        errors = ["SyntaxError in bad.py", "FileNotFoundError: missing.py"]
        result = format_all_findings(findings, "coupling", errors=errors)
        assert "Scanner Errors" in result
        assert "SyntaxError in bad.py" in result
        assert "FileNotFoundError" in result

    def test_empty_findings_list(self):
        """Empty findings still produces a header."""
        result = format_all_findings([], "coupling")
        assert "0 findings" in result


class TestExtractSnippet:
    """Tests for code snippet extraction."""

    def test_extract_from_valid_file(self):
        """Extracts lines around the target with >>> marker."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
        ) as f:
            for i in range(1, 21):
                f.write(f"line {i}\n")
            temp_path = f.name

        try:
            rel = os.path.basename(temp_path)
            snippet = _extract_snippet(tempfile.gettempdir(), rel, 10, context=3)
            assert snippet is not None
            assert ">>>" in snippet
            assert "line 10" in snippet
            # Context lines should be there
            assert "line 8" in snippet
            assert "line 12" in snippet
        finally:
            os.unlink(temp_path)

    def test_missing_file_returns_none(self):
        """Non-existent file returns None."""
        result = _extract_snippet("/nonexistent", "missing.py", 1)
        assert result is None

    def test_line_at_file_start(self):
        """Line 1 still works (no negative indexing)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
        ) as f:
            f.write("first line\nsecond line\nthird line\n")
            temp_path = f.name

        try:
            rel = os.path.basename(temp_path)
            snippet = _extract_snippet(tempfile.gettempdir(), rel, 1, context=2)
            assert snippet is not None
            assert "first line" in snippet
            assert ">>>" in snippet
        finally:
            os.unlink(temp_path)


class TestContextAPIEndpoint:
    """Tests for the /scans/<name>/context API endpoint."""

    def test_context_endpoint_no_results(self, client):
        """Context endpoint with no scan data returns fallback message."""
        response = client.get("/scans/coupling/context")
        assert response.status_code == 200
        data = response.get_json()
        assert "No scan results" in data["text"]

    def test_context_endpoint_with_findings(self, client, db):
        """Context endpoint returns formatted findings."""
        import json
        from models import ScanResult

        scan = ScanResult(
            project="vms",
            scanner="security",
            finding_count=1,
            result_json=json.dumps(
                {
                    "findings": [
                        {
                            "file": "routes/auth.py",
                            "line": 10,
                            "message": "Unprotected POST route",
                            "severity": "critical",
                            "details": {"blueprint": "auth"},
                        }
                    ],
                    "scanned_files": 5,
                    "duration_ms": 50,
                }
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/scans/security/context")
        assert response.status_code == 200
        data = response.get_json()
        assert "CRITICAL" in data["text"]
        assert "Unprotected POST route" in data["text"]
        assert "`auth`" in data["text"]

    def test_context_endpoint_sorts_by_file(self, client, db):
        """Findings are sorted by file to match template sort order.

        The scan detail template sorts findings by file. If the API
        returns them in a different order, per-finding copy buttons
        grab the wrong finding. This test inserts findings in reverse
        file order and verifies the API output is sorted.
        """
        import json
        from models import ScanResult

        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=2,
            result_json=json.dumps(
                {
                    "findings": [
                        {
                            "file": "z_routes/last.py",
                            "line": 1,
                            "message": "Z finding (should appear second)",
                            "severity": "warning",
                            "details": {},
                        },
                        {
                            "file": "a_routes/first.py",
                            "line": 1,
                            "message": "A finding (should appear first)",
                            "severity": "critical",
                            "details": {},
                        },
                    ],
                    "scanned_files": 2,
                    "duration_ms": 10,
                }
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/scans/coupling/context")
        assert response.status_code == 200
        text = response.get_json()["text"]

        # A finding should appear before Z finding in the output
        a_pos = text.index("A finding (should appear first)")
        z_pos = text.index("Z finding (should appear second)")
        assert (
            a_pos < z_pos
        ), "Findings should be sorted by file — 'a_routes' before 'z_routes'"

    def test_context_wire_format_matches_js_consumer(self, client, db):
        """The API response format must match the JS split/index contract.

        The scan_detail.html JavaScript does:
            sections = text.split('\\n---\\n')
            findingText = sections[idx + 1]

        This means:
        1. sections[0] must be ONLY the header (no findings)
        2. sections[1] must be the first finding
        3. sections[N+1] must be the Nth finding (0-indexed)

        This test verifies that contract with 2 findings. Without this,
        we can have sort-order tests pass while per-finding copy grabs
        the wrong finding (as happened with the header/finding fusion bug).
        """
        import json
        from models import ScanResult

        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=2,
            result_json=json.dumps(
                {
                    "findings": [
                        {
                            "file": "b.py",
                            "line": 1,
                            "message": "MARKER_B",
                            "severity": "warning",
                            "details": {},
                        },
                        {
                            "file": "a.py",
                            "line": 1,
                            "message": "MARKER_A",
                            "severity": "critical",
                            "details": {},
                        },
                    ],
                    "scanned_files": 2,
                    "duration_ms": 10,
                }
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/scans/coupling/context")
        text = response.get_json()["text"]
        sections = text.split("\n---\n")

        # Must have header + 2 findings = 3 sections
        assert len(sections) >= 3, (
            f"Expected at least 3 sections (header + 2 findings), "
            f"got {len(sections)}"
        )

        # sections[0] = header only, no finding markers
        assert "MARKER_A" not in sections[0], "Header section must not contain findings"
        assert "MARKER_B" not in sections[0], "Header section must not contain findings"

        # sections[1] = first finding (sorted: a.py before b.py)
        assert (
            "MARKER_A" in sections[1]
        ), "sections[1] should contain the first finding (a.py)"

        # sections[2] = second finding
        assert (
            "MARKER_B" in sections[2]
        ), "sections[2] should contain the second finding (b.py)"
