"""Tests for Phase 3a: WorkItem CRUD, Feature CRUD, Status Tracker Importer, and CLI commands."""

import tempfile
from pathlib import Path

from models import WorkItem, Feature


# --- WorkItem CRUD Route Tests ---


class TestWorkItemList:
    """Tests for GET /work-items."""

    def test_work_item_list_empty(self, client):
        """Work board loads with no items."""
        response = client.get("/work-items")
        assert response.status_code == 200
        assert b"Work Board" in response.data
        assert b"0 items" in response.data

    def test_work_item_list_shows_items(self, client, db):
        """Work board shows created items."""
        item = WorkItem(
            project="test", title="Fix auth bug", priority="high", status="backlog"
        )
        db.session.add(item)
        db.session.commit()

        response = client.get("/work-items")
        assert response.status_code == 200
        assert b"Fix auth bug" in response.data
        assert b"1 items" in response.data

    def test_work_item_list_filter_by_status(self, client, db):
        """Status filter hides non-matching items."""
        db.session.add(WorkItem(project="test", title="Backlog item", status="backlog"))
        db.session.add(WorkItem(project="test", title="Done item", status="done"))
        db.session.commit()

        response = client.get("/work-items?status=backlog")
        assert response.status_code == 200
        assert b"Backlog item" in response.data
        assert b"Done item" not in response.data

    def test_work_item_list_filter_by_priority(self, client, db):
        """Priority filter returns matching items."""
        db.session.add(WorkItem(project="test", title="High prio", priority="high"))
        db.session.add(WorkItem(project="test", title="Low prio", priority="low"))
        db.session.commit()

        response = client.get("/work-items?priority=high")
        assert response.status_code == 200
        assert b"High prio" in response.data
        assert b"Low prio" not in response.data

    def test_work_item_list_hides_archived_by_default(self, client, db):
        """Archived items are hidden unless toggle is on."""
        active = WorkItem(project="test", title="Active item", status="backlog")
        archived = WorkItem(
            project="test", title="Archived item", status="done", is_archived=True
        )
        db.session.add_all([active, archived])
        db.session.commit()

        response = client.get("/work-items")
        assert b"Active item" in response.data
        assert b"Archived item" not in response.data

    def test_work_item_list_shows_archived_when_toggled(self, client, db):
        """Archived items appear when toggle is on."""
        archived = WorkItem(
            project="test", title="Archived item", status="done", is_archived=True
        )
        db.session.add(archived)
        db.session.commit()

        response = client.get("/work-items?archived=1")
        assert b"Archived item" in response.data


class TestWorkItemCreate:
    """Tests for POST /work-items/new."""

    def test_create_form_loads(self, client):
        """New item form renders."""
        response = client.get("/work-items/new")
        assert response.status_code == 200
        assert b"New Work Item" in response.data

    def test_create_item(self, client, db):
        """POST creates a new WorkItem and redirects."""
        response = client.post(
            "/work-items/new",
            data={
                "title": "New test bug",
                "category": "bug",
                "priority": "high",
                "status": "backlog",
                "project": "vms",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"New test bug" in response.data

        item = WorkItem.query.filter_by(title="New test bug").first()
        assert item is not None
        assert item.category == "bug"
        assert item.priority == "high"


class TestWorkItemDetail:
    """Tests for GET /work-items/<id>."""

    def test_detail_loads(self, client, db):
        """Detail page renders for existing item."""
        item = WorkItem(project="test", title="Detail test item", status="backlog")
        db.session.add(item)
        db.session.commit()

        response = client.get(f"/work-items/{item.id}")
        assert response.status_code == 200
        assert b"Detail test item" in response.data

    def test_detail_404_for_missing(self, client):
        """Detail returns 404 for non-existent item."""
        response = client.get("/work-items/99999")
        assert response.status_code == 404


class TestWorkItemActions:
    """Tests for complete and archive actions."""

    def test_complete_item(self, client, db):
        """POST to complete marks item as done."""
        item = WorkItem(project="test", title="Complete me", status="in_progress")
        db.session.add(item)
        db.session.commit()

        response = client.post(f"/work-items/{item.id}/complete", follow_redirects=True)
        assert response.status_code == 200

        refreshed = db.session.get(WorkItem, item.id)
        assert refreshed.status == "done"
        assert refreshed.completed_at is not None

    def test_archive_item(self, client, db):
        """POST to archive sets is_archived and redirects to list."""
        item = WorkItem(project="test", title="Archive me", status="done")
        db.session.add(item)
        db.session.commit()

        response = client.post(f"/work-items/{item.id}/archive", follow_redirects=True)
        assert response.status_code == 200

        refreshed = db.session.get(WorkItem, item.id)
        assert refreshed.is_archived is True


# --- Feature CRUD Route Tests ---


class TestFeatureList:
    """Tests for GET /features."""

    def test_feature_list_empty(self, client):
        """Features page loads with no features."""
        response = client.get("/features")
        assert response.status_code == 200
        assert b"Feature Lifecycle" in response.data
        assert b"0 features tracked" in response.data

    def test_feature_list_shows_features(self, client, db):
        """Features page shows created features."""
        f = Feature(
            project="test",
            name="Test feature",
            domain="Core",
            implementation_status="implemented",
        )
        db.session.add(f)
        db.session.commit()

        response = client.get("/features")
        assert response.status_code == 200
        assert b"Test feature" in response.data

    def test_feature_list_filter_by_domain(self, client, db):
        """Domain filter shows only matching features."""
        db.session.add(
            Feature(
                project="test",
                name="Virtual feat",
                domain="Virtual Events",
                implementation_status="implemented",
            )
        )
        db.session.add(
            Feature(
                project="test",
                name="Email feat",
                domain="Email",
                implementation_status="pending",
            )
        )
        db.session.commit()

        response = client.get("/features?domain=Virtual Events")
        assert response.status_code == 200
        assert b"Virtual feat" in response.data
        assert b"Email feat" not in response.data


class TestFeatureCreate:
    """Tests for POST /features/new."""

    def test_create_form_loads(self, client):
        """New feature form renders."""
        response = client.get("/features/new")
        assert response.status_code == 200
        assert b"New Feature" in response.data

    def test_create_feature(self, client, db):
        """POST creates a new Feature and redirects."""
        response = client.post(
            "/features/new",
            data={
                "name": "New test feature",
                "domain": "Virtual Events",
                "status": "requested",
                "implementation_status": "pending",
                "project": "vms",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"New test feature" in response.data

        feat = Feature.query.filter_by(name="New test feature").first()
        assert feat is not None
        assert feat.domain == "Virtual Events"


class TestFeatureShip:
    """Tests for the ship action."""

    def test_ship_feature(self, client, db):
        """Ship sets status, date_shipped, and auto-calculates next_review."""
        f = Feature(
            project="test",
            name="Ship me",
            status="in_progress",
            implementation_status="implemented",
        )
        db.session.add(f)
        db.session.commit()

        response = client.post(f"/features/{f.id}/ship", follow_redirects=True)
        assert response.status_code == 200

        refreshed = db.session.get(Feature, f.id)
        assert refreshed.status == "shipped"
        assert refreshed.date_shipped is not None
        assert refreshed.next_review is not None


# --- Status Tracker Importer Tests ---


class TestStatusTrackerImporter:
    """Tests for the status tracker importer."""

    SAMPLE_TRACKER = """# VMS Development Status Tracker

**Last Updated:** March 2026
**Total Functional Requirements:** ~5

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | **Implemented** |
| 🔧 | **Partial** |
| 📋 | **Pending** |
| 🔮 | **Future** |
| ➖ | **N/A** |

---

## Quick Summary

| Domain | Total | ✅ | 🔧 | 📋 | 🔮 |
|--------|-------|----|----|----|-----|
| [Test Domain](#test-domain) | 5 | 2 | 1 | 1 | 1 |

---

## Test Domain

> File: [test.md](../requirements/test.md)

### Core Features

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-TEST-001 | First feature | ✅ | TC-100, TC-101 |
| FR-TEST-002 | Second feature | 🔧 | Needs work |
| FR-TEST-003 | Third feature | 📋 | |

### Future Features

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-TEST-004 | Future feature | 🔮 | Phase 5 |
| FR-TEST-005 | Not applicable | ➖ | Context only |
"""

    def test_parse_all_status_symbols(self, app, db):
        """Importer correctly maps all 5 status symbols."""
        from importers.status_tracker_importer import StatusTrackerImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.SAMPLE_TRACKER)
            f.flush()
            path = f.name

        importer = StatusTrackerImporter()
        stats = importer.import_from_file(path, project="test")

        assert stats["created"] == 5
        assert stats["errors"] == []

        # Verify each status mapping
        f1 = Feature.query.filter_by(requirement_id="FR-TEST-001").first()
        assert f1.implementation_status == "implemented"
        assert f1.status == "shipped"

        f2 = Feature.query.filter_by(requirement_id="FR-TEST-002").first()
        assert f2.implementation_status == "partial"

        f3 = Feature.query.filter_by(requirement_id="FR-TEST-003").first()
        assert f3.implementation_status == "pending"

        f4 = Feature.query.filter_by(requirement_id="FR-TEST-004").first()
        assert f4.implementation_status == "future"

        f5 = Feature.query.filter_by(requirement_id="FR-TEST-005").first()
        assert f5.implementation_status == "na"

        Path(path).unlink()

    def test_extracts_domain_from_section_headers(self, app, db):
        """Importer assigns domain from ## headings."""
        from importers.status_tracker_importer import StatusTrackerImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.SAMPLE_TRACKER)
            f.flush()
            path = f.name

        importer = StatusTrackerImporter()
        importer.import_from_file(path, project="test")

        f1 = Feature.query.filter_by(requirement_id="FR-TEST-001").first()
        assert f1.domain == "Test Domain"

        Path(path).unlink()

    def test_extracts_test_cases(self, app, db):
        """Importer extracts test case references from notes."""
        from importers.status_tracker_importer import StatusTrackerImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.SAMPLE_TRACKER)
            f.flush()
            path = f.name

        importer = StatusTrackerImporter()
        importer.import_from_file(path, project="test")

        f1 = Feature.query.filter_by(requirement_id="FR-TEST-001").first()
        test_cases = f1.get_test_cases()
        assert len(test_cases) > 0
        assert "TC-100, TC-101" in test_cases[0]

        Path(path).unlink()

    def test_upsert_updates_existing(self, app, db):
        """Re-import updates existing features instead of duplicating."""
        from importers.status_tracker_importer import StatusTrackerImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.SAMPLE_TRACKER)
            f.flush()
            path = f.name

        importer = StatusTrackerImporter()

        # First import
        stats1 = importer.import_from_file(path, project="test")
        assert stats1["created"] == 5

        # Second import (should update, not create)
        stats2 = importer.import_from_file(path, project="test")
        assert stats2["created"] == 0
        assert stats2["updated"] == 5

        # Total count should still be 5
        assert Feature.query.count() == 5

        Path(path).unlink()

    def test_skips_summary_and_legend(self, app, db):
        """Importer skips Quick Summary and Status Legend sections."""
        from importers.status_tracker_importer import StatusTrackerImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.SAMPLE_TRACKER)
            f.flush()
            path = f.name

        importer = StatusTrackerImporter()
        importer.import_from_file(path, project="test")

        # Should NOT have created features from the summary table
        assert Feature.query.count() == 5

        Path(path).unlink()


# --- Bug/Feature Quick-Capture CLI Tests ---


class TestBugCaptureCLI:
    """Tests for the bug quick-capture CLI command."""

    def test_bug_creates_work_item(self, app, db, monkeypatch):
        """cli.py bug creates a WorkItem with category='bug'."""
        from click.testing import CliRunner
        import cli as cli_module

        # Patch get_app to return the test app
        monkeypatch.setattr(cli_module, "get_app", lambda: app)

        runner = CliRunner()
        result = runner.invoke(
            cli_module.cli, ["bug", "-p", "vms", "--title", "Test crash on login"]
        )
        assert result.exit_code == 0
        assert "Bug created" in result.output

        item = WorkItem.query.filter_by(title="Test crash on login").first()
        assert item is not None
        assert item.category == "bug"
        assert item.priority == "medium"
        assert item.status == "backlog"

    def test_bug_with_priority(self, app, db, monkeypatch):
        """cli.py bug respects --priority flag."""
        from click.testing import CliRunner
        import cli as cli_module

        monkeypatch.setattr(cli_module, "get_app", lambda: app)

        runner = CliRunner()
        result = runner.invoke(
            cli_module.cli,
            ["bug", "-p", "vms", "--title", "Critical crash", "--priority", "critical"],
        )
        assert result.exit_code == 0

        item = WorkItem.query.filter_by(title="Critical crash").first()
        assert item is not None
        assert item.priority == "critical"


class TestFeatureRequestCLI:
    """Tests for the feature-request CLI command."""

    def test_feature_request_creates_work_item(self, app, db, monkeypatch):
        """cli.py feature-request creates a WorkItem with category='feature'."""
        from click.testing import CliRunner
        import cli as cli_module

        monkeypatch.setattr(cli_module, "get_app", lambda: app)

        runner = CliRunner()
        result = runner.invoke(
            cli_module.cli, ["feature-request", "-p", "vms", "--title", "Add dark mode"]
        )
        assert result.exit_code == 0
        assert "Feature request created" in result.output

        item = WorkItem.query.filter_by(title="Add dark mode").first()
        assert item is not None
        assert item.category == "feature"
        assert item.priority == "medium"
