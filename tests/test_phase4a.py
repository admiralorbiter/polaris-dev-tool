"""Tests for Phase 4a: Actionability — scan drill-down, finding→WorkItem, review queue."""

import json
from datetime import date, timedelta

from models import Feature, ScanResult, WorkItem


class TestDashboardScannerCards:
    """Dashboard shows per-scanner cards with finding counts."""

    def test_dashboard_shows_scanner_cards(self, client, db):
        """Dashboard renders per-scanner finding counts."""
        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=2,
            severity="warning",
            result_json=json.dumps(
                {
                    "findings": [
                        {
                            "file": "routes/a.py",
                            "line": 10,
                            "message": "Missing template",
                            "severity": "warning",
                        },
                        {
                            "file": "routes/b.py",
                            "line": 20,
                            "message": "Orphaned template",
                            "severity": "warning",
                        },
                    ],
                    "scanned_files": 5,
                    "duration_ms": 100,
                }
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/")
        assert response.status_code == 200
        assert b"Coupling" in response.data
        assert b"2 findings" in response.data

    def test_dashboard_scanner_all_clear(self, client, db):
        """Scanner with 0 findings shows checkmark."""
        scan = ScanResult(
            project="vms",
            scanner="security",
            finding_count=0,
            result_json=json.dumps(
                {"findings": [], "scanned_files": 10, "duration_ms": 50}
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/")
        assert response.status_code == 200
        assert "✅".encode("utf-8") in response.data

    def test_dashboard_no_scans(self, client):
        """Dashboard shows No scans message when no scans exist."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"No scans yet" in response.data

    def test_scan_panel_links_to_scan_list(self, client, db):
        """Scan panel links to /scans."""
        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=0,
            result_json=json.dumps({"findings": []}),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/")
        assert b"/scans" in response.data


class TestDashboardReviewQueue:
    """Dashboard shows feature review queue."""

    def test_review_queue_shows_due_count(self, client, db):
        """Dashboard shows count of features due for review."""
        feature = Feature(
            project="vms",
            name="Test feature",
            status="shipped",
            implementation_status="implemented",
            next_review=date.today() + timedelta(days=7),
        )
        db.session.add(feature)
        db.session.commit()

        response = client.get("/")
        assert response.status_code == 200
        assert b"Due for Review" in response.data
        assert b"1" in response.data

    def test_review_queue_overdue_shows_alert(self, client, db):
        """Overdue reviews show danger styling."""
        feature = Feature(
            project="vms",
            name="Overdue feature",
            status="shipped",
            implementation_status="implemented",
            next_review=date.today() - timedelta(days=5),
        )
        db.session.add(feature)
        db.session.commit()

        response = client.get("/")
        assert b"Overdue" in response.data
        assert b"panel-alert" in response.data

    def test_review_queue_no_reviews(self, client):
        """No reviews due shows clean state."""
        response = client.get("/")
        assert b"No features due for review" in response.data

    def test_review_panel_links_to_filtered_list(self, client):
        """Review panel links to /features?review=due."""
        response = client.get("/")
        assert b"review=due" in response.data


class TestFeatureReviewFilter:
    """Feature list supports review=due filter."""

    def test_review_due_filter(self, client, db):
        """review=due shows only features due within 14 days."""
        due_soon = Feature(
            project="vms",
            name="Due soon",
            requirement_id="FR-DUE",
            next_review=date.today() + timedelta(days=7),
        )
        not_due = Feature(
            project="vms",
            name="Not due",
            requirement_id="FR-NOTDUE",
            next_review=date.today() + timedelta(days=60),
        )
        db.session.add_all([due_soon, not_due])
        db.session.commit()

        response = client.get("/features?review=due")
        assert b"Due soon" in response.data
        assert b"Not due" not in response.data

    def test_review_due_filter_includes_overdue(self, client, db):
        """review=due includes overdue features."""
        overdue = Feature(
            project="vms",
            name="Overdue feature",
            requirement_id="FR-OVER",
            next_review=date.today() - timedelta(days=10),
        )
        db.session.add(overdue)
        db.session.commit()

        response = client.get("/features?review=due")
        assert b"Overdue feature" in response.data

    def test_review_due_filter_empty(self, client):
        """review=due with no features shows empty state."""
        response = client.get("/features?review=due")
        assert response.status_code == 200


class TestFindingToWorkItem:
    """Finding→WorkItem pipeline via query params."""

    def test_prepopulated_form_from_finding(self, client):
        """GET /work-items/new?from_finding=1 pre-populates the form."""
        response = client.get(
            "/work-items/new?from_finding=1"
            "&title=Missing+template+test.html"
            "&priority=high"
            "&category=review"
            "&notes=coupling+scanner+finding"
        )
        assert response.status_code == 200
        assert b"Missing template test.html" in response.data
        assert b"review" in response.data

    def test_prepopulated_form_sets_priority(self, client):
        """Priority from severity mapping shows in the form."""
        response = client.get(
            "/work-items/new?from_finding=1"
            "&title=Unprotected+POST+route"
            "&priority=high"
            "&category=review"
        )
        assert response.status_code == 200
        # The form should have high priority pre-selected
        assert b"Unprotected POST route" in response.data

    def test_create_work_item_from_finding(self, client, db):
        """POST from pre-populated form creates the work item."""
        response = client.post(
            "/work-items/new",
            data={
                "title": "Missing template: test.html",
                "category": "review",
                "priority": "high",
                "notes": "[coupling scanner] routes/test.py line 10",
                "source_id": "SCAN-coupling-1",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        item = WorkItem.query.filter_by(source_id="SCAN-coupling-1").first()
        assert item is not None
        assert item.title == "Missing template: test.html"
        assert item.category == "review"
        assert item.priority == "high"

    def test_scan_detail_has_create_button(self, client, db):
        """Scan detail page shows Create Item button for each finding."""
        scan = ScanResult(
            project="vms",
            scanner="coupling",
            finding_count=1,
            result_json=json.dumps(
                {
                    "findings": [
                        {
                            "file": "routes/test.py",
                            "line": 10,
                            "message": "Missing template",
                            "severity": "warning",
                        }
                    ],
                    "scanned_files": 1,
                    "duration_ms": 10,
                }
            ),
        )
        db.session.add(scan)
        db.session.commit()

        response = client.get("/scans/coupling")
        assert b"Create Item" in response.data
        assert b"from_finding" in response.data


class TestDashboardNavigation:
    """All dashboard panels are clickable."""

    def test_work_items_panel_links(self, client):
        """Work Items panel links to /work-items."""
        response = client.get("/")
        assert b"/work-items" in response.data

    def test_features_panel_links(self, client):
        """Features panel links to /features."""
        response = client.get("/")
        assert b"/features" in response.data

    def test_footer_shows_phase_4a(self, client):
        """Footer shows Phase 4a: Actionability."""
        response = client.get("/")
        assert b"Phase 4a: Actionability" in response.data
