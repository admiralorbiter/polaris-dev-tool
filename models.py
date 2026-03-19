"""Database models for Polaris DevTools."""

import json
from datetime import datetime, timedelta, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# --- Helper for JSON fields ---


def json_loads_safe(value):
    """Safely load a JSON string, returning empty list if None/empty."""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def json_dumps_safe(value):
    """Safely dump a value to JSON string."""
    if value is None:
        return None
    return json.dumps(value)


# --- Models ---


class WorkItem(db.Model):
    """Tracks actionable work: tech debt, bugs, features, reviews.

    Source of truth for data exported to tech_debt.md.
    """

    __tablename__ = "work_item"

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    project = db.Column(db.String(50), nullable=False, index=True)
    source_id = db.Column(db.String(50), unique=True)
    title = db.Column(db.String(200), nullable=False)

    # Classification
    category = db.Column(db.String(30), nullable=False, default="tech_debt")
    priority = db.Column(db.String(10), default="medium")
    effort = db.Column(db.String(5))
    risk = db.Column(db.String(10))
    tags = db.Column(db.Text)

    # Status
    status = db.Column(db.String(20), default="backlog", index=True)
    is_archived = db.Column(db.Boolean, default=False, index=True)

    # Relationships
    dependencies = db.Column(db.Text)
    code_paths = db.Column(db.Text)

    # Content
    notes = db.Column(db.Text)
    resolution_summary = db.Column(db.Text)

    # Dates
    identified_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = db.Column(db.DateTime)

    def get_tags(self):
        return json_loads_safe(self.tags)

    def set_tags(self, value):
        self.tags = json_dumps_safe(value)

    def get_dependencies(self):
        return json_loads_safe(self.dependencies)

    def set_dependencies(self, value):
        self.dependencies = json_dumps_safe(value)

    def get_code_paths(self):
        return json_loads_safe(self.code_paths)

    def set_code_paths(self, value):
        self.code_paths = json_dumps_safe(value)

    def complete(self):
        """Mark this item as done."""
        self.status = "done"
        self.completed_at = datetime.now(timezone.utc)

    def archive(self):
        """Archive this item (hides from active board)."""
        self.is_archived = True

    def __repr__(self):
        return f"<WorkItem {self.source_id or self.id}: {self.title[:40]}>"


class Feature(db.Model):
    """Tracks feature lifecycle and FR status.

    Source of truth for data exported to development_status_tracker.md.
    """

    __tablename__ = "feature"

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    project = db.Column(db.String(50), nullable=False, index=True)
    requirement_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(200), nullable=False)
    domain = db.Column(db.String(50))

    # Ownership
    requested_by = db.Column(db.String(100))
    requirement_doc = db.Column(db.String(200))

    # Status
    status = db.Column(db.String(20), default="requested", index=True)
    implementation_status = db.Column(db.String(20), default="pending")

    # Testing
    test_cases = db.Column(db.Text)

    # Lifecycle
    date_requested = db.Column(db.Date)
    date_shipped = db.Column(db.Date)
    next_review = db.Column(db.Date)
    usage_metric = db.Column(db.Text)

    # Content
    code_paths = db.Column(db.Text)
    notes = db.Column(db.Text)
    last_activity = db.Column(db.DateTime)

    def get_test_cases(self):
        return json_loads_safe(self.test_cases)

    def set_test_cases(self, value):
        self.test_cases = json_dumps_safe(value)

    def ship(self, ship_date=None):
        """Mark feature as shipped and set 90-day review date."""
        self.date_shipped = ship_date or datetime.now(timezone.utc).date()
        self.next_review = self.date_shipped + timedelta(days=90)
        self.status = "shipped"
        self.implementation_status = "implemented"

    def __repr__(self):
        return f"<Feature {self.requirement_id or self.id}: {self.name[:40]}>"


class ScanResult(db.Model):
    """Cached scanner output for dashboard display and historical tracking."""

    __tablename__ = "scan_result"

    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(50), nullable=False, index=True)
    scanner = db.Column(db.String(30), nullable=False, index=True)
    scanner_version = db.Column(db.String(10), nullable=False, default="1.0")
    severity = db.Column(db.String(10))
    finding_count = db.Column(db.Integer, default=0)
    result_json = db.Column(db.Text)
    scanned_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    def get_results(self):
        return json_loads_safe(self.result_json)

    def __repr__(self):
        return f"<ScanResult {self.scanner}@{self.scanned_at}: {self.finding_count} findings>"


class SessionLog(db.Model):
    """Records dev session briefings and receipts."""

    __tablename__ = "session_log"

    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(50), nullable=False, index=True)

    # Timing
    started_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    ended_at = db.Column(db.DateTime)

    # Git context
    commit_range_start = db.Column(db.String(40))
    commit_range_end = db.Column(db.String(40))

    # Content
    briefing_json = db.Column(db.Text)
    receipt_json = db.Column(db.Text)
    files_changed = db.Column(db.Text)
    docs_exported = db.Column(db.Text)

    # Notes
    notes = db.Column(db.Text)

    def end_session(self, commit_sha=None):
        """End this session."""
        self.ended_at = datetime.now(timezone.utc)
        if commit_sha:
            self.commit_range_end = commit_sha

    @property
    def duration_minutes(self):
        """Session duration in minutes, or None if still active."""
        if not self.ended_at:
            return None
        delta = self.ended_at - self.started_at
        return int(delta.total_seconds() / 60)

    def __repr__(self):
        status = "active" if not self.ended_at else f"{self.duration_minutes}m"
        return f"<SessionLog {self.project} {self.started_at:%Y-%m-%d} ({status})>"


class ExportLog(db.Model):
    """Tracks export timestamps for dirty-flag detection."""

    __tablename__ = "export_log"

    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(50), nullable=False, index=True)
    target = db.Column(db.String(50), nullable=False)
    exported_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    file_path = db.Column(db.String(500))
    record_count = db.Column(db.Integer, default=0)
    git_staged = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<ExportLog {self.target}@{self.exported_at}>"


class HealthSnapshot(db.Model):
    """Point-in-time health score snapshot, recorded on each briefing/receipt."""

    __tablename__ = "health_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(50), nullable=False, index=True)
    recorded_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    score = db.Column(db.Integer, nullable=False)  # 0-100
    components_json = db.Column(db.Text)  # JSON dict of component scores
    trigger = db.Column(db.String(20), default="briefing")  # 'briefing' or 'receipt'

    def get_components(self):
        """Return components as a dict."""
        if not self.components_json:
            return {}
        try:
            return json.loads(self.components_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def __repr__(self):
        return f"<HealthSnapshot {self.project} {self.recorded_at:%Y-%m-%d} score={self.score}>"
