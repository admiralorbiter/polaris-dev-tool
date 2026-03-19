"""Tests for tech debt importer — covering parsing edge cases and resolved archive."""

import tempfile
from pathlib import Path

from models import WorkItem


class TestTechDebtImporterParsing:
    """Tests for the tech debt importer's markdown parsing."""

    FULL_TECH_DEBT_DOC = """# Tech Debt Tracker

Active technical debt items.

---

## TD-001: Auth decorator inconsistency

**Created:** 2025-11-15 · **Priority:** High

Routes use inconsistent auth decorators. Some use `@login_required`,
others use `@admin_required` with no clear policy.

---

## TD-002: Legacy cleanup *(Deferred)*

**Created:** 2025-10-01

Old code that needs removal but isn't blocking anything.

---

## TD-003: Database migration ✅ RESOLVED

**Created:** 2025-09-15

Already fixed this one.

---

## Priority Order

Ordered by **what best unblocks future work**:

| Priority | ID | Item | Effort |
| --- | --- | --- | --- |
| 1 | **TD-001** | Auth decorator inconsistency | M |
| ~~2~~ | ~~**TD-003**~~ | ~~Database migration~~ ✅ | ~~S~~ |

> TD-002 is intentionally deferred.

---

## Resolved Archive

All resolved items, for historical reference:

| ID | Title | Resolved | Summary |
|----|-------|----------|---------|
| TD-010 | Old migration issue | 2025-08-01 | Completed in v1.5 |
| TD-011 | Dead code cleanup | N/A | — |
"""

    def test_parses_active_items(self, app, db):
        """Importer finds active tech debt items from ## headers."""
        from importers.tech_debt_importer import TechDebtImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.FULL_TECH_DEBT_DOC)
            f.flush()
            path = f.name

        importer = TechDebtImporter()
        stats = importer.import_from_file(path, project="test")

        # Should have created items for active + resolved archive
        assert stats["errors"] == []

        # Check active item with priority
        td001 = WorkItem.query.filter_by(source_id="TD-001").first()
        assert td001 is not None
        assert td001.title == "Auth decorator inconsistency"
        assert td001.priority == "high"
        assert "inconsistent auth" in td001.notes.lower()

        Path(path).unlink()

    def test_parses_deferred_status(self, app, db):
        """Items with *(Deferred)* suffix get status='deferred'."""
        from importers.tech_debt_importer import TechDebtImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.FULL_TECH_DEBT_DOC)
            f.flush()
            path = f.name

        importer = TechDebtImporter()
        importer.import_from_file(path, project="test")

        td002 = WorkItem.query.filter_by(source_id="TD-002").first()
        assert td002 is not None
        assert td002.status == "deferred"
        assert "Legacy cleanup" in td002.title
        assert "*(Deferred)*" not in td002.title  # Cleaned from title

        Path(path).unlink()

    def test_parses_resolved_inline(self, app, db):
        """Items with ✅ RESOLVED in header get status='done'."""
        from importers.tech_debt_importer import TechDebtImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.FULL_TECH_DEBT_DOC)
            f.flush()
            path = f.name

        importer = TechDebtImporter()
        importer.import_from_file(path, project="test")

        td003 = WorkItem.query.filter_by(source_id="TD-003").first()
        assert td003 is not None
        assert td003.status == "done"
        assert "Database migration" in td003.title
        assert "✅" not in td003.title  # Cleaned

        Path(path).unlink()

    def test_parses_resolved_archive(self, app, db):
        """Importer parses the Resolved Archive table."""
        from importers.tech_debt_importer import TechDebtImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.FULL_TECH_DEBT_DOC)
            f.flush()
            path = f.name

        importer = TechDebtImporter()
        importer.import_from_file(path, project="test")

        td010 = WorkItem.query.filter_by(source_id="TD-010").first()
        assert td010 is not None
        assert td010.title == "Old migration issue"
        assert td010.is_archived is True
        assert td010.resolution_summary == "Completed in v1.5"
        assert td010.completed_at is not None

        # N/A date should not crash
        td011 = WorkItem.query.filter_by(source_id="TD-011").first()
        assert td011 is not None
        assert td011.completed_at is None

        Path(path).unlink()

    def test_merges_effort_from_priority_table(self, app, db):
        """Effort from priority table rows with strikethrough markup get merged."""
        from importers.tech_debt_importer import TechDebtImporter

        # Use a doc where the priority table has properly formatted struck rows
        doc = """# Tech Debt

---

## TD-050: First task

**Created:** 2025-11-15

Some notes.

---

## TD-051: Second task

**Created:** 2025-11-15

More notes.

---

## Priority Order

| Priority | ID | Item | Effort |
| --- | --- | --- | --- |
| ~1~ | **TD-050** | First task | L |
| ~2~ | **TD-051** | Second task | S |
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(doc)
            f.flush()
            path = f.name

        importer = TechDebtImporter()
        importer.import_from_file(path, project="test")

        td050 = WorkItem.query.filter_by(source_id="TD-050").first()
        assert td050 is not None
        assert td050.effort == "L"

        td051 = WorkItem.query.filter_by(source_id="TD-051").first()
        assert td051.effort == "S"

        Path(path).unlink()

    def test_parses_created_date(self, app, db):
        """Created date from metadata line is parsed into identified_date."""
        from importers.tech_debt_importer import TechDebtImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.FULL_TECH_DEBT_DOC)
            f.flush()
            path = f.name

        importer = TechDebtImporter()
        importer.import_from_file(path, project="test")

        td001 = WorkItem.query.filter_by(source_id="TD-001").first()
        assert td001.identified_date is not None
        assert td001.identified_date.year == 2025
        assert td001.identified_date.month == 11

        Path(path).unlink()

    def test_empty_file_returns_no_items(self, app, db):
        """Empty markdown file creates no items."""
        from importers.tech_debt_importer import TechDebtImporter

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Tech Debt Tracker\n\nNo items yet.\n")
            f.flush()
            path = f.name

        importer = TechDebtImporter()
        stats = importer.import_from_file(path, project="test")

        assert stats["created"] == 0
        assert stats["errors"] == []

        Path(path).unlink()
