"""Tests for Phase 5d: Doc Engine.

Covers:
- Phase 5d-1: ManagedDoc model, ChangelogExporter, export sync API, auto-dirty
- Phase 5d-2: HybridDocExporter (slot parsing, slot rendering), doc routes, doc seeding
"""

from datetime import datetime, timezone

import pytest

from models import Feature, ManagedDoc, WorkItem


# ══════════════════════════════════════════════════════════════
# ManagedDoc Model
# ══════════════════════════════════════════════════════════════


class TestManagedDocModel:
    """Test ManagedDoc model creation and constraints."""

    def test_managed_doc_creation(self, app, db):
        """ManagedDoc creates with correct defaults."""
        doc = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog",
            tier="generated",
            output_path="docs/changelog.md",
            exporter_key="changelog_v1",
        )
        db.session.add(doc)
        db.session.commit()

        assert doc.id is not None
        assert doc.project == "vms"
        assert doc.doc_key == "changelog"
        assert doc.is_dirty is True  # default
        assert doc.last_exported_at is None
        assert doc.created_at is not None

    def test_managed_doc_unique_constraint(self, app, db):
        """Same project+doc_key can't duplicate."""
        doc1 = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog",
            tier="generated",
        )
        doc2 = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog Copy",
            tier="generated",
        )
        db.session.add(doc1)
        db.session.commit()

        db.session.add(doc2)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()

    def test_managed_doc_different_projects_ok(self, app, db):
        """Same doc_key in different projects is fine."""
        doc1 = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog VMS",
            tier="generated",
        )
        doc2 = ManagedDoc(
            project="other",
            doc_key="changelog",
            title="Changelog Other",
            tier="generated",
        )
        db.session.add(doc1)
        db.session.add(doc2)
        db.session.commit()

        assert doc1.id != doc2.id

    def test_managed_doc_repr(self, app, db):
        """Repr shows doc_key and dirty flag."""
        doc = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog",
            tier="generated",
            is_dirty=True,
        )
        assert "changelog" in repr(doc)
        assert "DIRTY" in repr(doc)

        doc.is_dirty = False
        assert "DIRTY" not in repr(doc)


# ══════════════════════════════════════════════════════════════
# ChangelogExporter
# ══════════════════════════════════════════════════════════════


class TestChangelogExporter:
    """Test ChangelogExporter rendering."""

    def _make_item(self, db, **overrides):
        """Helper to create a WorkItem with defaults."""
        defaults = {
            "project": "vms",
            "title": "Test Item",
            "category": "feature",
            "priority": "medium",
            "status": "done",
            "source_id": "FT-001",
            "updated_at": datetime(2026, 3, 15, tzinfo=timezone.utc),
        }
        defaults.update(overrides)
        item = WorkItem(**defaults)
        db.session.add(item)
        db.session.commit()
        return item

    def test_changelog_empty(self, app, db):
        """No done items → renders header + empty message."""
        from exporters.changelog_exporter import ChangelogExporter

        exporter = ChangelogExporter()
        content = exporter.render("vms")

        assert "# Changelog" in content
        assert "No completed items yet" in content

    def test_changelog_single_item(self, app, db):
        """1 done feature → correct section."""
        from exporters.changelog_exporter import ChangelogExporter

        self._make_item(db, title="Draft Review Queue", source_id="FT-001")

        exporter = ChangelogExporter()
        content = exporter.render("vms")

        assert "# Changelog" in content
        assert "## March 2026" in content
        assert "### Features" in content
        assert "**FT-001** Draft Review Queue" in content

    def test_changelog_multiple_categories(self, app, db):
        """Mix of feature+bug+tech_debt → 3 sections."""
        from exporters.changelog_exporter import ChangelogExporter

        self._make_item(db, title="Add widgets", source_id="FT-001", category="feature")
        self._make_item(db, title="Fix login", source_id="BUG-001", category="bug")
        self._make_item(
            db, title="Refactor SQL", source_id="TD-001", category="tech_debt"
        )

        exporter = ChangelogExporter()
        content = exporter.render("vms")

        assert "### Features" in content
        assert "### Bug Fixes" in content
        assert "### Tech Debt" in content
        assert "**FT-001**" in content
        assert "**BUG-001**" in content
        assert "**TD-001**" in content

    def test_changelog_groups_by_month(self, app, db):
        """Items from different months → separate headings."""
        from exporters.changelog_exporter import ChangelogExporter

        self._make_item(
            db,
            title="March item",
            source_id="FT-001",
            updated_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        self._make_item(
            db,
            title="February item",
            source_id="FT-002",
            updated_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
        )

        exporter = ChangelogExporter()
        content = exporter.render("vms")

        assert "## March 2026" in content
        assert "## February 2026" in content
        # March should appear before February (newest first)
        march_pos = content.index("March 2026")
        feb_pos = content.index("February 2026")
        assert march_pos < feb_pos

    def test_changelog_excludes_non_done(self, app, db):
        """In-progress and backlog items excluded."""
        from exporters.changelog_exporter import ChangelogExporter

        self._make_item(db, title="Done item", status="done", source_id="FT-001")
        self._make_item(db, title="WIP item", status="in_progress", source_id="FT-002")
        self._make_item(db, title="Backlog item", status="backlog", source_id="FT-003")

        exporter = ChangelogExporter()
        content = exporter.render("vms")

        assert "Done item" in content
        assert "WIP item" not in content
        assert "Backlog item" not in content

    def test_changelog_no_source_id(self, app, db):
        """Items without source_id render title only (no bold empty string)."""
        from exporters.changelog_exporter import ChangelogExporter

        self._make_item(db, title="Mystery fix", source_id=None)

        exporter = ChangelogExporter()
        content = exporter.render("vms")

        assert "Mystery fix" in content
        assert "**None**" not in content

    def test_changelog_export_writes_file(self, app, db, tmp_path):
        """Export method writes file and records export log."""
        from exporters.changelog_exporter import ChangelogExporter
        from models import ExportLog

        self._make_item(db, title="Test item", source_id="FT-001")

        exporter = ChangelogExporter()
        output_path = tmp_path / "changelog.md"
        result = exporter.export("vms", output_path)

        assert output_path.exists()
        assert "# Changelog" in output_path.read_text(encoding="utf-8")
        assert result["record_count"] == 1

        # Check ExportLog was created
        log = ExportLog.query.filter_by(project="vms", target="changelog").first()
        assert log is not None


# ══════════════════════════════════════════════════════════════
# Export Sync API Endpoint
# ══════════════════════════════════════════════════════════════


class TestExportSyncAPI:
    """Test POST /api/export/sync endpoint."""

    def _seed_managed_docs(self, db):
        """Create the standard managed docs."""
        docs = [
            ManagedDoc(
                project="vms",
                doc_key="changelog",
                title="Changelog",
                tier="generated",
                exporter_key="changelog_v1",
                output_path="docs/changelog.md",
                is_dirty=True,
            ),
            ManagedDoc(
                project="vms",
                doc_key="tech_debt",
                title="Tech Debt",
                tier="generated",
                exporter_key="tech_debt_v1",
                output_path="docs/tech_debt.md",
                is_dirty=False,
            ),
        ]
        for d in docs:
            db.session.add(d)
        db.session.commit()

    def test_export_sync_no_dirty(self, app, client, db):
        """When no docs are dirty, returns empty exported list."""
        doc = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog",
            tier="generated",
            exporter_key="changelog_v1",
            is_dirty=False,
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.post(
            "/api/export/sync",
            json={"project": "vms"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["exported"] == []
        assert data["total_dirty"] == 0

    def test_export_sync_unknown_project(self, app, client, db):
        """Unknown project returns 404."""
        resp = client.post(
            "/api/export/sync",
            json={"project": "nonexistent"},
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_export_sync_clears_dirty(self, app, client, db, tmp_path, monkeypatch):
        """After sync, is_dirty = False and last_exported_at is set."""
        # Create a config that points to tmp_path
        monkeypatch.setattr(
            "routes.api._get_project_config",
            lambda p: {"project_root": str(tmp_path)} if p == "vms" else None,
        )

        doc = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog",
            tier="generated",
            exporter_key="changelog_v1",
            output_path="changelog.md",
            is_dirty=True,
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.post(
            "/api/export/sync",
            json={"project": "vms"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "changelog" in data["exported"]

        # Verify dirty was cleared
        db.session.refresh(doc)
        assert doc.is_dirty is False
        assert doc.last_exported_at is not None

    def test_export_sync_skips_unknown_exporter(self, app, client, db, monkeypatch):
        """Doc with unknown exporter_key is skipped."""
        monkeypatch.setattr(
            "routes.api._get_project_config",
            lambda p: {"project_root": "."} if p == "vms" else None,
        )

        doc = ManagedDoc(
            project="vms",
            doc_key="mystery_doc",
            title="Mystery",
            tier="generated",
            exporter_key="nonexistent_v1",
            is_dirty=True,
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.post(
            "/api/export/sync",
            json={"project": "vms"},
            content_type="application/json",
        )
        data = resp.get_json()
        assert "mystery_doc" in data["skipped"]


# ══════════════════════════════════════════════════════════════
# Auto-Dirty on WorkItem Status Change
# ══════════════════════════════════════════════════════════════


class TestAutoDirty:
    """Test that completing/editing WorkItems marks docs as dirty."""

    def _seed_docs(self, db):
        """Create standard managed docs with is_dirty=False."""
        for doc_key in ["changelog", "tech_debt", "status_tracker"]:
            doc = ManagedDoc(
                project="vms",
                doc_key=doc_key,
                title=doc_key.replace("_", " ").title(),
                tier="generated",
                exporter_key=f"{doc_key}_v1",
                is_dirty=False,
            )
            db.session.add(doc)
        db.session.commit()

    def test_complete_marks_changelog_dirty(self, app, client, db):
        """WorkItem.complete() → changelog is marked dirty."""
        self._seed_docs(db)

        item = WorkItem(
            project="vms",
            title="Test feature",
            category="feature",
            priority="medium",
            status="in_progress",
        )
        db.session.add(item)
        db.session.commit()

        client.post(f"/work-items/{item.id}/complete")

        changelog = ManagedDoc.query.filter_by(
            project="vms", doc_key="changelog"
        ).first()
        assert changelog.is_dirty is True

        # tech_debt should NOT be dirty (item is a feature, not tech_debt)
        td = ManagedDoc.query.filter_by(project="vms", doc_key="tech_debt").first()
        assert td.is_dirty is False

    def test_complete_tech_debt_marks_both_dirty(self, app, client, db):
        """Completing tech_debt item → both changelog AND tech_debt dirty."""
        self._seed_docs(db)

        item = WorkItem(
            project="vms",
            title="Refactor SQL",
            category="tech_debt",
            priority="medium",
            status="in_progress",
        )
        db.session.add(item)
        db.session.commit()

        client.post(f"/work-items/{item.id}/complete")

        changelog = ManagedDoc.query.filter_by(
            project="vms", doc_key="changelog"
        ).first()
        td = ManagedDoc.query.filter_by(project="vms", doc_key="tech_debt").first()
        assert changelog.is_dirty is True
        assert td.is_dirty is True

    def test_edit_to_done_marks_dirty(self, app, client, db):
        """Editing status to 'done' via edit form → marks changelog dirty."""
        self._seed_docs(db)

        item = WorkItem(
            project="vms",
            title="Test feature",
            category="feature",
            priority="medium",
            status="in_progress",
        )
        db.session.add(item)
        db.session.commit()

        client.post(
            f"/work-items/{item.id}/edit",
            data={
                "title": "Test feature",
                "category": "feature",
                "priority": "medium",
                "status": "done",
            },
        )

        changelog = ManagedDoc.query.filter_by(
            project="vms", doc_key="changelog"
        ).first()
        assert changelog.is_dirty is True

    def test_edit_non_done_does_not_dirty(self, app, client, db):
        """Editing status to something other than 'done' doesn't dirty docs."""
        self._seed_docs(db)

        item = WorkItem(
            project="vms",
            title="Test feature",
            category="feature",
            priority="medium",
            status="backlog",
        )
        db.session.add(item)
        db.session.commit()

        client.post(
            f"/work-items/{item.id}/edit",
            data={
                "title": "Test feature",
                "category": "feature",
                "priority": "medium",
                "status": "in_progress",
            },
        )

        changelog = ManagedDoc.query.filter_by(
            project="vms", doc_key="changelog"
        ).first()
        assert changelog.is_dirty is False


# ══════════════════════════════════════════════════════════════
# Phase 5d-2: HybridDocExporter — Slot Parsing
# ══════════════════════════════════════════════════════════════


class TestHybridDocExporter:
    """Test HybridDocExporter slot parsing and rendering."""

    TEMPLATE_ONE_SLOT = """# My Doc

Some authored prose.

<!-- devtools:slot:recent_changes -->
Old content here
<!-- /devtools:slot -->

More authored prose.
"""

    TEMPLATE_TWO_SLOTS = """# Mixed Doc

<!-- devtools:slot:recent_changes -->
<!-- /devtools:slot -->

Paragraph between slots.

<!-- devtools:slot:route_table -->
<!-- /devtools:slot -->

Footer.
"""

    TEMPLATE_NO_SLOTS = """# Plain Doc

No markers here.
"""

    def test_slot_parsing_basic(self, app, db):
        """Extract slots from template with one slot."""
        from exporters.hybrid_exporter import HybridDocExporter

        exporter = HybridDocExporter()
        slots = exporter.extract_slots(self.TEMPLATE_ONE_SLOT)

        assert len(slots) == 1
        assert slots[0]["name"] == "recent_changes"
        assert "Old content here" in slots[0]["existing_content"]

    def test_slot_parsing_multiple(self, app, db):
        """Extract slots from template with two slots."""
        from exporters.hybrid_exporter import HybridDocExporter

        exporter = HybridDocExporter()
        slots = exporter.extract_slots(self.TEMPLATE_TWO_SLOTS)

        assert len(slots) == 2
        assert slots[0]["name"] == "recent_changes"
        assert slots[1]["name"] == "route_table"

    def test_empty_slots(self, app, db):
        """Template with no slots returns empty list, render returns unchanged."""
        from exporters.hybrid_exporter import HybridDocExporter

        exporter = HybridDocExporter()
        slots = exporter.extract_slots(self.TEMPLATE_NO_SLOTS)
        assert slots == []

        # Render should return unchanged text
        result = exporter.render("vms", self.TEMPLATE_NO_SLOTS)
        assert result == self.TEMPLATE_NO_SLOTS

    def test_slot_replacement_preserves_prose(self, app, db):
        """Slot content is replaced; authored prose is preserved."""
        from exporters.hybrid_exporter import HybridDocExporter

        exporter = HybridDocExporter()
        result = exporter.render("vms", self.TEMPLATE_ONE_SLOT)

        # Authored prose preserved
        assert "Some authored prose." in result
        assert "More authored prose." in result

        # Old content replaced
        assert "Old content here" not in result

        # Markers preserved
        assert "<!-- devtools:slot:recent_changes -->" in result
        assert "<!-- /devtools:slot -->" in result

    def test_unknown_slot_renders_message(self, app, db):
        """Unknown slot name renders a message instead of crashing."""
        from exporters.hybrid_exporter import HybridDocExporter

        template = """<!-- devtools:slot:nonexistent -->
<!-- /devtools:slot -->"""
        exporter = HybridDocExporter()
        result = exporter.render("vms", template)

        assert "Unknown slot: nonexistent" in result

    def test_recent_changes_slot(self, app, db):
        """recent_changes slot renders done WorkItems."""
        from exporters.hybrid_exporter import HybridDocExporter

        WorkItem.query.delete()
        items = [
            WorkItem(
                project="vms",
                title="Add widgets",
                source_id="FT-001",
                category="feature",
                status="done",
                priority="medium",
                updated_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
            ),
            WorkItem(
                project="vms",
                title="Fix crash",
                source_id="BUG-001",
                category="bug",
                status="done",
                priority="medium",
                updated_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
            ),
        ]
        for item in items:
            db.session.add(item)
        db.session.commit()

        exporter = HybridDocExporter()
        result = exporter.render("vms", self.TEMPLATE_ONE_SLOT)

        assert "**FT-001** Add widgets" in result
        assert "**BUG-001** Fix crash" in result
        assert "**Features**" in result
        assert "**Bug Fixes**" in result

    def test_recent_changes_empty(self, app, db):
        """recent_changes with no done items renders 'no changes' message."""
        from exporters.hybrid_exporter import HybridDocExporter

        exporter = HybridDocExporter()
        result = exporter.render("vms", self.TEMPLATE_ONE_SLOT)

        assert "No recent changes" in result


# ══════════════════════════════════════════════════════════════
# Phase 5d-2: Doc Routes
# ══════════════════════════════════════════════════════════════


class TestDocRoutes:
    """Test doc list and detail page routes."""

    def test_docs_list_page(self, app, client, db):
        """GET /docs returns 200 with doc list."""
        resp = client.get("/docs")
        assert resp.status_code == 200
        assert b"Managed Documents" in resp.data

    def test_docs_list_shows_seeded_docs(self, app, client, db):
        """GET /docs shows seeded docs."""
        doc = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog",
            tier="generated",
            exporter_key="changelog_v1",
            is_dirty=True,
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.get("/docs")
        assert resp.status_code == 200
        assert b"Changelog" in resp.data
        assert b"Dirty" in resp.data

    def test_doc_detail_page(self, app, client, db):
        """GET /docs/changelog returns 200 with doc details."""
        doc = ManagedDoc(
            project="vms",
            doc_key="changelog",
            title="Changelog",
            tier="generated",
            exporter_key="changelog_v1",
        )
        db.session.add(doc)
        db.session.commit()

        resp = client.get("/docs/changelog")
        assert resp.status_code == 200
        assert b"Changelog" in resp.data

    def test_doc_detail_404(self, app, client, db):
        """GET /docs/nonexistent returns 404."""
        resp = client.get("/docs/nonexistent")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# Phase 5d-2: Doc Seeding
# ══════════════════════════════════════════════════════════════


class TestDocSeeding:
    """Test POST /api/docs/seed endpoint."""

    def test_doc_seed_creates_records(self, app, client, db):
        """Seed creates default managed doc records."""
        resp = client.post(
            "/api/docs/seed",
            json={"project": "vms"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "changelog" in data["created"]
        assert "tech_debt" in data["created"]
        assert "status_tracker" in data["created"]

        # Verify records exist
        assert ManagedDoc.query.filter_by(project="vms").count() == 3

    def test_doc_seed_idempotent(self, app, client, db):
        """Double-seed doesn't create duplicates."""
        client.post(
            "/api/docs/seed", json={"project": "vms"}, content_type="application/json"
        )
        resp = client.post(
            "/api/docs/seed", json={"project": "vms"}, content_type="application/json"
        )

        data = resp.get_json()
        assert data["created"] == []
        assert len(data["existing"]) == 3

        # Still only 3 records
        assert ManagedDoc.query.filter_by(project="vms").count() == 3


# ══════════════════════════════════════════════════════════════
# Phase 5d-3: Feature Auto-Dirty + FR Import
# ══════════════════════════════════════════════════════════════


class TestFeatureAutoDirty:
    """Test that Feature mutations mark status_tracker as dirty."""

    def _seed_status_tracker(self, db):
        """Create a status_tracker ManagedDoc set to clean."""
        doc = ManagedDoc(
            project="vms",
            doc_key="status_tracker",
            title="Development Status Tracker",
            tier="generated",
            exporter_key="status_tracker_v1",
            is_dirty=False,
        )
        db.session.add(doc)
        db.session.commit()
        return doc

    def test_feature_create_marks_dirty(self, app, client, db):
        """Creating a Feature marks status_tracker as dirty."""
        self._seed_status_tracker(db)

        client.post(
            "/features/new",
            data={
                "name": "New Feature",
                "domain": "Virtual Events",
                "status": "requested",
                "implementation_status": "pending",
            },
        )

        doc = ManagedDoc.query.filter_by(
            project="vms", doc_key="status_tracker"
        ).first()
        assert doc.is_dirty is True

    def test_feature_edit_marks_dirty(self, app, client, db):
        """Editing a Feature marks status_tracker as dirty."""
        self._seed_status_tracker(db)

        feature = Feature(
            project="vms",
            name="Test Feature",
            requirement_id="FR-TEST-001",
            domain="Testing",
            implementation_status="pending",
        )
        db.session.add(feature)
        db.session.commit()

        client.post(
            f"/features/{feature.id}/edit",
            data={
                "name": "Updated Feature",
                "domain": "Testing",
                "implementation_status": "implemented",
            },
        )

        doc = ManagedDoc.query.filter_by(
            project="vms", doc_key="status_tracker"
        ).first()
        assert doc.is_dirty is True

    def test_feature_ship_marks_dirty(self, app, client, db):
        """Shipping a Feature marks status_tracker as dirty."""
        self._seed_status_tracker(db)

        feature = Feature(
            project="vms",
            name="Ship Me",
            requirement_id="FR-SHIP-001",
            domain="Testing",
            implementation_status="partial",
        )
        db.session.add(feature)
        db.session.commit()

        client.post(f"/features/{feature.id}/ship")

        doc = ManagedDoc.query.filter_by(
            project="vms", doc_key="status_tracker"
        ).first()
        assert doc.is_dirty is True

        # Feature itself should be shipped
        feature = Feature.query.get(feature.id)
        assert feature.implementation_status == "implemented"


class TestFeatureImport:
    """Test POST /api/features/import endpoint."""

    def test_import_creates_features(self, app, client, db):
        """Import creates new Feature records."""
        resp = client.post(
            "/api/features/import",
            json={
                "project": "vms",
                "features": [
                    {
                        "requirement_id": "FR-V-001",
                        "name": "Session Scheduling",
                        "domain": "Virtual Events",
                        "implementation_status": "implemented",
                    },
                    {
                        "requirement_id": "FR-V-002",
                        "name": "Attendance Tracking",
                        "domain": "Virtual Events",
                        "implementation_status": "partial",
                    },
                ],
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["created"] == 2
        assert data["updated"] == 0

        assert Feature.query.filter_by(requirement_id="FR-V-001").count() == 1

    def test_import_upserts_existing(self, app, client, db):
        """Import updates existing features, doesn't duplicate."""
        feature = Feature(
            project="vms",
            requirement_id="FR-V-001",
            name="Old Name",
            domain="Virtual Events",
            implementation_status="pending",
        )
        db.session.add(feature)
        db.session.commit()

        resp = client.post(
            "/api/features/import",
            json={
                "project": "vms",
                "features": [
                    {
                        "requirement_id": "FR-V-001",
                        "name": "Updated Name",
                        "domain": "Virtual Events",
                        "implementation_status": "implemented",
                    },
                ],
            },
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["created"] == 0
        assert data["updated"] == 1

        updated = Feature.query.filter_by(requirement_id="FR-V-001").first()
        assert updated.name == "Updated Name"
        assert updated.implementation_status == "implemented"

    def test_import_marks_dirty(self, app, client, db):
        """Import marks status_tracker as dirty."""
        doc = ManagedDoc(
            project="vms",
            doc_key="status_tracker",
            title="Status Tracker",
            tier="generated",
            exporter_key="status_tracker_v1",
            is_dirty=False,
        )
        db.session.add(doc)
        db.session.commit()

        client.post(
            "/api/features/import",
            json={
                "project": "vms",
                "features": [
                    {
                        "requirement_id": "FR-TEST-001",
                        "name": "Test Feature",
                        "domain": "Testing",
                    },
                ],
            },
            content_type="application/json",
        )

        doc = ManagedDoc.query.filter_by(
            project="vms", doc_key="status_tracker"
        ).first()
        assert doc.is_dirty is True


# ══════════════════════════════════════════════════════════════
# Phase 5d-4: Feature Docs + WorkItem Linking
# ══════════════════════════════════════════════════════════════


class TestFeatureDocSlug:
    """Test Feature.doc_slug field and slugify utility."""

    def test_doc_slug_field(self, app, db):
        """Feature can store a doc_slug."""
        feature = Feature(
            project="vms",
            name="Draft Review Queue",
            requirement_id="FR-TEST-SLUG",
            doc_slug="draft-review-queue",
        )
        db.session.add(feature)
        db.session.commit()

        loaded = Feature.query.filter_by(requirement_id="FR-TEST-SLUG").first()
        assert loaded.doc_slug == "draft-review-queue"

    def test_slugify(self, app, db):
        """FeatureDocExporter.slugify generates clean slugs."""
        from exporters.feature_doc_exporter import FeatureDocExporter

        assert FeatureDocExporter.slugify("Draft Review Queue") == "draft-review-queue"
        assert FeatureDocExporter.slugify("FR: Session Import") == "fr-session-import"
        assert FeatureDocExporter.slugify("  Spaces & Special! ") == "spaces-special"


class TestFeatureWorkItemLink:
    """Test Feature→WorkItem FK relationship."""

    def test_workitem_feature_link(self, app, db):
        """WorkItem.feature_id links to Feature."""
        feature = Feature(
            project="vms",
            name="Test Feature",
            requirement_id="FR-LINK-001",
        )
        db.session.add(feature)
        db.session.flush()

        wi = WorkItem(
            project="vms",
            title="Related task",
            source_id="TD-LINK-001",
            category="tech_debt",
            feature_id=feature.id,
        )
        db.session.add(wi)
        db.session.commit()

        # Load via relationship
        loaded = Feature.query.filter_by(requirement_id="FR-LINK-001").first()
        assert len(loaded.work_items) == 1
        assert loaded.work_items[0].title == "Related task"


class TestFeatureDocExporter:
    """Test FeatureDocExporter rendering."""

    def test_render_feature(self, app, db):
        """render_feature produces metadata table."""
        from exporters.feature_doc_exporter import FeatureDocExporter

        feature = Feature(
            project="vms",
            name="Session Scheduling",
            requirement_id="FR-VIRTUAL-001",
            domain="Virtual Events",
            implementation_status="implemented",
            doc_slug="session-scheduling",
        )
        db.session.add(feature)
        db.session.commit()

        exporter = FeatureDocExporter()
        result = exporter.render_feature(feature)

        assert "# Session Scheduling" in result
        assert "`FR-VIRTUAL-001`" in result
        assert "Virtual Events" in result
        assert "implemented" in result

    def test_render_feature_with_work_items(self, app, db):
        """render_feature includes linked WorkItems table."""
        from exporters.feature_doc_exporter import FeatureDocExporter

        feature = Feature(
            project="vms",
            name="Attendance Tracking",
            requirement_id="FR-VIRTUAL-002",
            domain="Virtual Events",
            implementation_status="partial",
            doc_slug="attendance-tracking",
        )
        db.session.add(feature)
        db.session.flush()

        wi = WorkItem(
            project="vms",
            title="Fix attendance import",
            source_id="BUG-001",
            category="bug",
            status="done",
            feature_id=feature.id,
        )
        db.session.add(wi)
        db.session.commit()

        exporter = FeatureDocExporter()
        result = exporter.render_feature(feature)

        assert "## Related Work Items" in result
        assert "BUG-001" in result
        assert "Fix attendance import" in result

    def test_render_empty(self, app, db):
        """render with no doc_slug features returns message."""
        from exporters.feature_doc_exporter import FeatureDocExporter

        exporter = FeatureDocExporter()
        result = exporter.render("vms")
        assert "No features with doc_slug" in result
