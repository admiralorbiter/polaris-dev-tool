# Data Models

> Complete field specifications for all database models.

**Last Updated:** March 2026

---

## Overview

DevTools uses 4 core models stored in SQLite (WAL mode):

| Model | Purpose | Records |
|:------|:--------|:--------|
| `WorkItem` | Tech debt, bugs, features, reviews | ~60 initial (from VMS tech_debt.md) |
| `Feature` | FR tracking and feature lifecycle | ~203 initial (from VMS status tracker) |
| `ScanResult` | Cached scanner output | Grows with each scan |
| `SessionLog` | Dev session history | Grows with each session |

---

## WorkItem

Tracks actionable work — tech debt items, bugs, feature requests, scheduled reviews. This model owns the data that gets exported to `tech_debt.md`.

```python
class WorkItem(db.Model):
    __tablename__ = "work_item"

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    project = db.Column(db.String(50), nullable=False, index=True)
    source_id = db.Column(db.String(50), unique=True)  # "TD-046", "BUG-003"
    title = db.Column(db.String(200), nullable=False)

    # Classification
    category = db.Column(db.String(30), nullable=False)
    priority = db.Column(db.String(10), default="medium")
    effort = db.Column(db.String(5))     # S, M, L, XL
    risk = db.Column(db.String(10))      # low, medium, high
    tags = db.Column(db.Text)            # JSON array

    # Status
    status = db.Column(db.String(20), default="backlog")
    is_archived = db.Column(db.Boolean, default=False)

    # Relationships
    dependencies = db.Column(db.Text)    # JSON: ["TD-042"]
    code_paths = db.Column(db.Text)      # JSON: ["routes/virtual/usage.py"]

    # Content
    notes = db.Column(db.Text)
    resolution_summary = db.Column(db.Text)

    # Dates
    identified_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
```

### Field Reference

| Field | Type | Required | Example |
|:------|:-----|:---------|:--------|
| `project` | String(50) | ✅ | `"vms"`, `"kc_pathways"` |
| `source_id` | String(50) | — | `"TD-046"`, `"BUG-003"` |
| `title` | String(200) | ✅ | `"Virtual Computation Duplication"` |
| `category` | String(30) | ✅ | `tech_debt`, `bug`, `feature`, `review`, `cleanup` |
| `priority` | String(10) | — | `critical`, `high`, `medium`, `low` |
| `effort` | String(5) | — | `S`, `M`, `L`, `XL` |
| `risk` | String(10) | — | `low`, `medium`, `high` |
| `tags` | JSON array | — | `["salesforce", "virtual"]` |
| `status` | String(20) | — | `backlog`, `in_progress`, `done`, `deferred` |
| `is_archived` | Boolean | — | `false` (default); `true` for resolved items |
| `dependencies` | JSON array | — | `["TD-042"]` — blocked-by items |
| `code_paths` | JSON array | — | `["routes/virtual/usage/computation.py"]` |
| `notes` | Text | — | Description, context, proposed fix |
| `resolution_summary` | Text | — | How the item was resolved |
| `identified_date` | Date | — | When the issue was first discovered |
| `due_date` | Date | — | For scheduled reviews or deadlines |
| `completed_at` | DateTime | — | Auto-set when status → `done` |

### Status Transitions

```
backlog → in_progress → done
                      → deferred
```

When `status` changes to `done`:
- `completed_at` is auto-set
- `is_archived` remains `false` until explicitly archived

### JSON Field Conventions

All JSON fields store arrays as strings:
```python
# Writing
item.tags = json.dumps(["salesforce", "virtual"])
item.dependencies = json.dumps(["TD-042"])

# Reading
tags = json.loads(item.tags) if item.tags else []
```

---

## Feature

Tracks feature lifecycle and functional requirement status. This model owns the data that gets exported to `development_status_tracker.md`.

```python
class Feature(db.Model):
    __tablename__ = "feature"

    id = db.Column(db.Integer, primary_key=True)

    # Identity
    project = db.Column(db.String(50), nullable=False, index=True)
    requirement_id = db.Column(db.String(50), unique=True)  # "FR-VIRTUAL-207"
    name = db.Column(db.String(200), nullable=False)
    domain = db.Column(db.String(50))  # "Virtual Events", "District Suite"

    # Ownership
    requested_by = db.Column(db.String(100))  # "staff", "users", "internal"
    requirement_doc = db.Column(db.String(200))  # source file path

    # Status
    status = db.Column(db.String(20), default="requested")
    implementation_status = db.Column(db.String(20), default="pending")

    # Testing
    test_cases = db.Column(db.Text)  # JSON: ["TC-250", "TC-260"]

    # Lifecycle
    date_requested = db.Column(db.Date)
    date_shipped = db.Column(db.Date)
    next_review = db.Column(db.Date)  # Auto: date_shipped + 90 days
    usage_metric = db.Column(db.Text)  # JSON: adoption signals

    # Content
    code_paths = db.Column(db.Text)  # JSON
    notes = db.Column(db.Text)
    last_activity = db.Column(db.DateTime)  # from git
```

### Status Values

**`status`** — lifecycle stage:

| Value | Meaning |
|:------|:--------|
| `requested` | Feature has been asked for |
| `in_progress` | Actively being developed |
| `shipped` | Deployed to production |
| `adopted` | Post-90-day review: confirmed useful |
| `under_review` | 90-day review period active |
| `deprecated` | Marked for removal |
| `removed` | Code deleted |

**`implementation_status`** — maps to status tracker symbols:

| Value | Symbol | Meaning |
|:------|:-------|:--------|
| `implemented` | ✅ | Has test coverage |
| `partial` | 🔧 | Partially implemented |
| `pending` | 📋 | Not yet implemented |
| `future` | 🔮 | Planned for future phase |
| `na` | ➖ | Not applicable |

### 90-Day Review Auto-Set

When `date_shipped` is set:
```python
feature.next_review = feature.date_shipped + timedelta(days=90)
feature.status = "shipped"
```

---

## ScanResult

Cached scanner output for dashboard display and historical tracking.

```python
class ScanResult(db.Model):
    __tablename__ = "scan_result"

    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(50), nullable=False, index=True)
    scanner = db.Column(db.String(30), nullable=False)         # "coupling", "security"
    scanner_version = db.Column(db.String(10), nullable=False) # "1.0"
    severity = db.Column(db.String(10))    # "critical", "warning", "info"
    finding_count = db.Column(db.Integer, default=0)
    result_json = db.Column(db.Text)       # Full scanner output
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### Querying Patterns

```python
# Latest results for a project
ScanResult.query.filter_by(project="vms").order_by(ScanResult.scanned_at.desc()).first()

# Critical findings only
ScanResult.query.filter_by(project="vms", severity="critical").all()

# Trend: finding counts over time
db.session.query(
    ScanResult.scanned_at, ScanResult.finding_count
).filter_by(project="vms", scanner="coupling").order_by(ScanResult.scanned_at).all()
```

---

## SessionLog

Records dev session briefings and receipts for historical analysis.

```python
class SessionLog(db.Model):
    __tablename__ = "session_log"

    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(50), nullable=False, index=True)

    # Timing
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime)

    # Git context
    commit_range_start = db.Column(db.String(40))  # SHA at session start
    commit_range_end = db.Column(db.String(40))     # SHA at session end

    # Content
    briefing_json = db.Column(db.Text)     # Pre-session snapshot
    receipt_json = db.Column(db.Text)      # Post-session 9-layer matrix
    files_changed = db.Column(db.Text)     # JSON array
    docs_exported = db.Column(db.Text)     # JSON array of exported doc paths

    # Notes
    notes = db.Column(db.Text)
```

---

## Database Configuration

```python
# config.py
SQLALCHEMY_DATABASE_URI = "sqlite:///instance/devtools.db"
SQLALCHEMY_ENGINE_OPTIONS = {
    "connect_args": {"check_same_thread": False},
}

# Enable WAL mode on connection
@event.listens_for(Engine, "connect")
def set_sqlite_wal(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
```

WAL mode prevents "database is locked" errors when running CLI scans alongside the web dashboard.
