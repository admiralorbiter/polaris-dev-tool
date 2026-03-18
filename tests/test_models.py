"""Tests for database models."""

import json
from datetime import datetime, date, timedelta

from models import WorkItem, Feature, ScanResult, SessionLog, ExportLog


class TestWorkItem:
    """Tests for the WorkItem model."""

    def test_create_basic(self, db):
        """WorkItem can be created with required fields."""
        item = WorkItem(
            project="vms",
            title="Fix broken import",
            category="bug",
        )
        db.session.add(item)
        db.session.commit()

        assert item.id is not None
        assert item.project == "vms"
        assert item.status == "backlog"
        assert item.is_archived is False
        assert item.priority == "medium"

    def test_create_with_source_id(self, db):
        """WorkItem stores source_id for tracking."""
        item = WorkItem(
            project="vms",
            source_id="TD-046",
            title="Virtual Computation Duplication",
            category="tech_debt",
            priority="high",
            effort="L",
            risk="medium",
        )
        db.session.add(item)
        db.session.commit()

        fetched = WorkItem.query.filter_by(source_id="TD-046").first()
        assert fetched is not None
        assert fetched.title == "Virtual Computation Duplication"
        assert fetched.effort == "L"

    def test_json_tags(self, db):
        """Tags field stores and retrieves JSON arrays."""
        item = WorkItem(project="vms", title="Test", category="tech_debt")
        item.set_tags(["salesforce", "virtual"])
        db.session.add(item)
        db.session.commit()

        fetched = WorkItem.query.get(item.id)
        assert fetched.get_tags() == ["salesforce", "virtual"]

    def test_json_tags_empty(self, db):
        """Empty tags returns empty list."""
        item = WorkItem(project="vms", title="Test", category="tech_debt")
        db.session.add(item)
        db.session.commit()

        assert item.get_tags() == []

    def test_json_dependencies(self, db):
        """Dependencies field stores and retrieves JSON arrays."""
        item = WorkItem(project="vms", title="Test", category="tech_debt")
        item.set_dependencies(["TD-042", "TD-043"])
        db.session.add(item)
        db.session.commit()

        assert item.get_dependencies() == ["TD-042", "TD-043"]

    def test_json_code_paths(self, db):
        """Code paths field stores and retrieves JSON arrays."""
        item = WorkItem(project="vms", title="Test", category="tech_debt")
        item.set_code_paths(["routes/virtual/usage.py"])
        db.session.add(item)
        db.session.commit()

        assert item.get_code_paths() == ["routes/virtual/usage.py"]

    def test_complete(self, db):
        """Completing an item sets status and timestamp."""
        item = WorkItem(project="vms", title="Test", category="tech_debt")
        db.session.add(item)
        db.session.commit()

        item.complete()
        db.session.commit()

        assert item.status == "done"
        assert item.completed_at is not None

    def test_archive(self, db):
        """Archiving an item hides from active board."""
        item = WorkItem(project="vms", title="Test", category="tech_debt")
        db.session.add(item)
        db.session.commit()

        item.archive()
        db.session.commit()

        assert item.is_archived is True

        # Archived items excluded from active query
        active = WorkItem.query.filter_by(is_archived=False).all()
        assert item not in active

    def test_repr(self, db):
        """String representation is useful for debugging."""
        item = WorkItem(
            project="vms", source_id="TD-001", title="Test item", category="tech_debt"
        )
        assert "TD-001" in repr(item)

    def test_source_id_unique(self, db):
        """Source IDs must be unique."""
        item1 = WorkItem(
            project="vms", source_id="TD-001", title="First", category="tech_debt"
        )
        item2 = WorkItem(
            project="vms", source_id="TD-001", title="Second", category="tech_debt"
        )
        db.session.add(item1)
        db.session.commit()

        db.session.add(item2)
        import sqlalchemy
        import pytest

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.session.commit()


class TestFeature:
    """Tests for the Feature model."""

    def test_create_basic(self, db):
        """Feature can be created with required fields."""
        feature = Feature(
            project="vms",
            name="Email notification system",
        )
        db.session.add(feature)
        db.session.commit()

        assert feature.id is not None
        assert feature.status == "requested"
        assert feature.implementation_status == "pending"

    def test_create_with_requirement_id(self, db):
        """Feature stores FR reference."""
        feature = Feature(
            project="vms",
            requirement_id="FR-EMAIL-801",
            name="Basic email sending",
            domain="Email",
        )
        db.session.add(feature)
        db.session.commit()

        fetched = Feature.query.filter_by(requirement_id="FR-EMAIL-801").first()
        assert fetched is not None
        assert fetched.domain == "Email"

    def test_ship_sets_review_date(self, db):
        """Shipping a feature auto-sets the 90-day review date."""
        feature = Feature(project="vms", name="Test feature")
        db.session.add(feature)
        db.session.commit()

        ship_date = date(2026, 3, 18)
        feature.ship(ship_date)
        db.session.commit()

        assert feature.status == "shipped"
        assert feature.implementation_status == "implemented"
        assert feature.date_shipped == ship_date
        assert feature.next_review == ship_date + timedelta(days=90)

    def test_test_cases_json(self, db):
        """Test cases field stores JSON arrays."""
        feature = Feature(project="vms", name="Test feature")
        feature.set_test_cases(["TC-250", "TC-260"])
        db.session.add(feature)
        db.session.commit()

        assert feature.get_test_cases() == ["TC-250", "TC-260"]


class TestScanResult:
    """Tests for the ScanResult model."""

    def test_create(self, db):
        """ScanResult can be created and stores findings."""
        result = ScanResult(
            project="vms",
            scanner="coupling",
            scanner_version="1.0",
            severity="warning",
            finding_count=3,
            result_json=json.dumps({"findings": []}),
        )
        db.session.add(result)
        db.session.commit()

        assert result.id is not None
        assert result.scanned_at is not None

    def test_ordering(self, db):
        """Latest scan results come first."""
        for i in range(3):
            db.session.add(
                ScanResult(
                    project="vms",
                    scanner="coupling",
                    finding_count=i,
                    scanned_at=datetime(2026, 3, 18, 10, 0, i),
                )
            )
        db.session.commit()

        latest = (
            ScanResult.query.filter_by(project="vms")
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )
        assert latest.finding_count == 2


class TestSessionLog:
    """Tests for the SessionLog model."""

    def test_create(self, db):
        """SessionLog can be created."""
        session = SessionLog(project="vms")
        db.session.add(session)
        db.session.commit()

        assert session.id is not None
        assert session.started_at is not None
        assert session.ended_at is None

    def test_end_session(self, db):
        """Ending a session records end time."""
        session = SessionLog(project="vms")
        db.session.add(session)
        db.session.commit()

        session.end_session(commit_sha="abc123")
        db.session.commit()

        assert session.ended_at is not None
        assert session.commit_range_end == "abc123"

    def test_duration(self, db):
        """Duration calculates correctly."""
        session = SessionLog(
            project="vms",
            started_at=datetime(2026, 3, 18, 10, 0, 0),
        )
        session.ended_at = datetime(2026, 3, 18, 11, 30, 0)
        assert session.duration_minutes == 90

    def test_duration_active_session(self, db):
        """Active sessions return None for duration."""
        session = SessionLog(project="vms")
        assert session.duration_minutes is None


class TestExportLog:
    """Tests for the ExportLog model."""

    def test_create(self, db):
        """ExportLog tracks export events."""
        log = ExportLog(
            project="vms",
            target="tech_debt",
            file_path="documentation/content/developer/tech_debt.md",
            record_count=51,
        )
        db.session.add(log)
        db.session.commit()

        assert log.id is not None
        assert log.exported_at is not None
        assert log.git_staged is False
