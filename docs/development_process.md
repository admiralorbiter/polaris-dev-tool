# Development Process

> How we build this tool — coding standards, testing strategy, and contribution patterns.

**Last Updated:** March 2026

---

## Quick Reference

```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Run
python app.py                          # Web UI on localhost:5001

# Test
python -m pytest                       # All tests
python -m pytest tests/test_scanners.py  # Specific file
python -m pytest -v --tb=short         # Verbose

# Quality
black .                                # Format
flake8 .                               # Lint
black --check . && flake8 .           # Both (pre-commit)

# Session Loop (see session_workflow.md for full spec)
python cli.py briefing -p vms         # Start session — 6-point briefing
python cli.py receipt -p vms          # End session — 9-layer receipt + hooks
python cli.py sessions -p vms        # View session history
```

---

## Session Loop

Every dev session is wrapped in a **briefing → work → receipt** cycle:

1. **Start:** `python cli.py briefing -p vms` — get a snapshot (git state, findings, WIPs, reviews, docs, exports) and start tracking
2. **Work:** code, commit, do your thing
3. **End:** `python cli.py receipt -p vms` — see what changed (9-layer matrix), auto-fix drift (export docs, create WorkItems), get a commit message

Sessions are stored in `SessionLog` and visible on the dashboard at `/sessions`.

> Full spec: [session_workflow.md](session_workflow.md)

## Feature & Phase Workflow

Every feature or phase follows this loop. **This is mandatory — do not skip the deep dive.**

### 1. Deep Dive (Before Starting)

Before writing any code for a new feature or phase:

1. **Research** — Examine the codebase, docs, and relevant patterns. Understand what exists.
2. **Options analysis** — Identify 2–3 approaches with tradeoffs:
   - What's simpler? What's more extensible? What introduces tech debt?
   - What aligns with existing patterns? What diverges and why?
3. **Present to user** — Lay out the options in a table:
   | Option | Pros | Cons | Tech Debt | Recommendation |
   |--------|------|------|-----------|---------------|
   Give a clear recommendation with reasoning.
4. **User decides** — Wait for approval before writing code.

> This mirrors the AI Collaboration Guide's "If tradeoffs are genuinely unclear, present 2 options max with a recommendation" rule, but makes it the default for all new work, not just unclear cases.

### 2. Build (After Approval)

- Follow the coding standards below
- Write tests alongside code (not after)
- Check against acceptance criteria in the roadmap

### 3. Verify

- All tests pass
- Acceptance criteria from roadmap are met
- No regressions in existing functionality

### 3.5 UI Feedback Session (Phases with UI Work)

Since we don't have a formal design spec, this step shapes the UI iteratively during development. **Do not skip to retro without this.**

**User walkthrough:**

1. User runs the app and clicks through all new/changed pages
2. User shares what feels right, what's confusing, and what's missing
3. User shares screenshots if anything looks off

**Agent UI review:**

1. Agent examines the current UI (via browser or screenshots)
2. Agent identifies quality-of-life improvements — small things that aren't on the roadmap but would make the tool more useful:
   - Layout/spacing issues
   - Missing empty states or loading indicators
   - Data that would be useful to surface but isn't shown
   - Navigation friction (extra clicks, unclear labels)
   - Quick wins that aren't in the roadmap but take < 30 min
3. Agent presents findings as a table:

| Issue | Category | Effort | Recommendation |
|-------|----------|--------|---------------|
| _e.g. "No way to re-run scan from UI"_ | Missing feature | M | Add later (Phase 3+) |
| _e.g. "Health score always shows '—'"_ | Dead UI element | S | Wire up now |

4. User decides which quick fixes to do now vs defer

> **Why this exists:** We're building without mockups or a UI designer. This step prevents us from shipping screens nobody's actually looked at, and catches low-hanging fruit before the codebase moves on.

> **Bias to action:** Effort estimates should be in AI-time, not human-time. If something takes < 30 min of AI work, **just do it** rather than listing it as a future item. Only defer items that genuinely belong in a different phase of the roadmap.

### 4. Retro (After Phase/Feature Completion)

After each phase or significant feature is complete, the user triggers a retro. The retro produces:

- **What shipped / didn't ship**
- **What went well**
- **What hurt / slowed us down**
- **Tech debt found or created**
- **Doc drift or misalignment**
- **Before next phase:** top fixes to do first
- **Action items** with effort and priority

| Item | Type (Debt/Process/Docs/Risk) | Why it matters | Effort (S/M/L) | Priority (P0/P1/P2) | Proposed next step |
|------|-------------------------------|----------------|-----------------|----------------------|--------------------|

> This is the retro format from the AI Collaboration Guide. It runs after every phase completion.

---

## Coding Standards

### Python Style

- **Formatter:** `black` (line length 88, default config)
- **Linter:** `flake8` (ignore E501 for long strings where black allows them)
- **Python:** 3.9+ (match VMS target)

### Naming Conventions

| Thing | Convention | Example |
|:------|:-----------|:--------|
| Files | `snake_case.py` | `coupling_audit.py` |
| Classes | `PascalCase` | `CouplingAuditScanner` |
| Functions | `snake_case` | `scan_routes()` |
| Constants | `UPPER_SNAKE` | `MAX_FINDING_COUNT` |
| CLI commands | `kebab-case` | `cli.py scan --scanner coupling` |
| Config keys | `snake_case` | `project_root`, `auth_decorators` |

### Docstrings

Use Google-style docstrings:

```python
def scan_routes(project_config: dict) -> ScanOutput:
    """Scan all route files for coupling issues.

    Parses Python AST of each route file, extracts render_template
    calls, and verifies referenced templates exist.

    Args:
        project_config: Loaded YAML config for the target project.

    Returns:
        ScanOutput with findings, scanned file count, and errors.

    Raises:
        FileNotFoundError: If project_root doesn't exist.
    """
```

### Import Order

1. Standard library
2. Third-party packages
3. Local imports

```python
import ast
import json
from pathlib import Path

from flask import Blueprint, jsonify
import yaml

from models import WorkItem, ScanResult
from scanners.base import Scanner, ScanOutput
```

---

## Testing Standards

### Tooling

- **Framework:** `pytest` (configured in `pyproject.toml`)
- **Run all tests:** `python -m pytest tests/ -v --tb=short`
- **Pre-commit:** `black` + `flake8` enforced on every commit

### Coverage Expectations

Every new feature or module must include:

1. **Happy path tests** — verify intended behavior works
2. **Edge case tests** — cover boundary conditions, empty inputs, malformed data
3. **Error handling tests** — verify graceful degradation (syntax errors, missing files, bad config)

### Test File Conventions

| Module | Test File | Coverage |
|:-------|:---------|:---------|
| `models.py` | `test_models.py` | Model creation, defaults, JSON fields, status transitions, ordering |
| `scanners/coupling_audit.py` | `test_scanners.py::TestCouplingAuditAST` + `EdgeCases` | AST parsing, template detection, auth decorators, empty files, no blueprint, dynamic templates |
| `scanners/security_audit.py` | `test_scanners.py::TestSecurityAudit` + `EdgeCases` | Protected/unprotected routes, all HTTP methods, public allowlist, missing config, object config |
| `importers/tech_debt_importer.py` | `test_scanners.py::TestTechDebtImporterEdgeCases` + `test_importers.py` | Backtick titles, ✅ RESOLVED, *(Deferred)*, empty files, malformed dates, resolved archive, effort merge |
| `importers/status_tracker_importer.py` | `test_phase3a.py::TestStatusTrackerImporter` | All 5 status symbols, domain extraction, test case extraction, upsert, skip summary/legend |
| `exporters/tech_debt_exporter.py` | `test_exporters.py::TestTechDebtExporter*` | Active/deferred/done items, resolved archive, priority table, file writing, ExportLog creation |
| `exporters/status_tracker_exporter.py` | `test_exporters.py::TestStatusTrackerExporter*` | Domain sections, summary table, status symbols, test case notes, file writing |
| `exporters/base.py` | `test_exporters.py::TestBaseExporter` | Dirty detection, table helper, status badge |
| `routes/dashboard.py` | `test_routes.py` + `test_phase3b.py` | Dashboard render, health score display, component bars |
| `routes/scans.py` | `test_scanners.py::TestScanRoutes` + `EdgeCases` | Empty state, populated state, findings display, nonexistent scanner |
| `routes/features.py` | `test_phase3a.py::TestFeature*` + `test_crud_routes.py` | List, filters, create, edit, ship, detail, review countdown |
| `routes/work_items.py` | `test_phase3a.py::TestWorkItem*` + `test_crud_routes.py` | List, filters, create, edit, complete, archive, category filter |
| `utils/context_formatter.py` | `test_context_formatter.py` | Single/batch formatting, null details, code snippets, sort order, wire format contract |
| `utils/health_score.py` | `test_phase3b.py::TestHealthScore` | 5-component scoring, boundary conditions, deductions |
| Phase 4a routes | `test_phase4a.py` | Scanner cards, review queue, finding→WorkItem pipeline, dashboard navigation, feature review filter |
| CLI (`cli.py`) | `test_phase3a.py::TestBugCaptureCLI` + `TestFeatureRequestCLI` | Bug quick-capture, feature-request, priority flags |

### Test Categories

- **Unit tests:** No Flask context needed. Test pure logic (parsers, AST analysis, regex)
- **Integration tests:** Use `client` and `db` fixtures. Test Flask routes with database
- **Web route tests:** Verify HTTP status codes, response content, and template rendering
- **Contract tests:** When backend produces structured output consumed by frontend (e.g., text split by delimiters), test the wire format the consumer depends on — not just the content

### Lessons Learned

**Test with realistic data, not just happy paths:**
- If a field can be `None` in production, include `None` in test fixtures (not just `{}` or omitted)
- If the consumer iterates a collection, test with 2+ items in adversarial order
- If the consumer splits text by a delimiter, verify the split produces the expected section count and each section contains the right content

> **Example:** The AI context packet API returns findings separated by `---`. The JS splits by that delimiter and indexes into sections. A test that only checks "finding A appears in the text" will pass even if the split puts it in the wrong section. A contract test checks `sections[1]` contains finding A specifically.

---

## Project Layout

```
polaris-devtools/
├── app.py              # Flask app factory
├── config.py           # Configuration classes
├── models.py           # SQLAlchemy models
├── cli.py              # Click CLI entry point
│
├── scanners/           # Pure Python (no Flask dependency)
│   ├── base.py         # Scanner protocol + ScanOutput/ScanFinding
│   └── *.py            # One file per scanner
│
├── exporters/          # DB → markdown renderers
│   ├── base.py         # Base exporter with dirty-flag logic
│   └── *.py            # One file per export format
│
├── importers/          # Markdown → DB parsers
│   └── *.py            # One file per import source
│
├── routes/             # Flask blueprints (web UI)
│   └── *.py            # One file per page/feature
│
├── templates/          # Jinja2 templates
├── static/             # CSS + JS
├── projects/           # Per-project YAML configs
├── docs/               # This documentation
└── tests/              # pytest tests
```

### Key Constraint: Scanners Are Pure Python

The `scanners/` directory must **never** import from Flask, SQLAlchemy, or any web framework code. Scanners receive a config dict and return a dataclass. This ensures scanners work identically from CLI and web contexts.

```python
# ✅ Correct — scanner is pure Python
from scanners.coupling_audit import CouplingAuditScanner
scanner = CouplingAuditScanner()
result = scanner.scan(project_config)

# ❌ Wrong — scanner imports Flask
from flask import current_app  # NEVER in scanners/
```

---

## Adding a New Scanner

1. **Create the file:** `scanners/my_scanner.py`

2. **Implement the protocol:**
```python
from scanners.base import Scanner, ScanOutput, ScanFinding

class MyScanner:
    name = "my_scanner"
    description = "Checks for X"
    version = "1.0"

    def scan(self, project_config: dict) -> ScanOutput:
        findings = []
        errors = []
        scanned = 0

        for filepath in self._get_files(project_config):
            scanned += 1
            try:
                # Your analysis here
                pass
            except (SyntaxError, UnicodeDecodeError) as e:
                errors.append(f"{filepath}: {e}")
                continue

        return ScanOutput(
            findings=findings,
            scanned_files=scanned,
            errors=errors,
            duration_ms=elapsed
        )
```

3. **Register in `scanners/__init__.py`:**
```python
from .my_scanner import MyScanner
SCANNER_REGISTRY["my_scanner"] = MyScanner
```

4. **Add tests:** `tests/test_my_scanner.py`

5. **Document:** Add a section to `docs/scanner_specs.md`

---

## Adding a New Exporter

1. **Create the file:** `exporters/my_exporter.py`

2. **Implement the base:**
```python
from exporters.base import BaseExporter

class MyExporter(BaseExporter):
    format_key = "my_format_v1"

    def render(self, records, project_config) -> str:
        """Render DB records to markdown string."""
        lines = ["<!-- Auto-generated by Polaris DevTools -->", ""]
        # Build markdown
        return "\n".join(lines)
```

3. **Register in `exporters/__init__.py`**

4. **Add to project YAML:**
```yaml
managed_docs:
  my_doc:
    path: "path/to/output.md"
    model: "WorkItem"
    format: "my_format_v1"
```

---

## Testing Strategy

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures (app, db, client)
├── test_models.py           # Model creation, validation, JSON fields
├── test_scanners.py         # Scanner output + edge cases + scan web routes
├── test_exporters.py        # Export format fidelity + BaseExporter utilities
├── test_importers.py        # Tech debt import parsing accuracy
├── test_context_formatter.py # AI context packet formatting + contract tests
├── test_routes.py           # Dashboard route smoke tests
├── test_crud_routes.py      # Feature + WorkItem edit/filter routes
├── test_phase3a.py          # Phase 3a: CRUD routes, status tracker import, CLI
├── test_phase3b.py          # Phase 3b: Health score, doc freshness, exporters
└── test_phase4a.py          # Phase 4a: Scanner cards, review queue, finding→WorkItem
```

### What Gets Tested

| Component | Test Type | What to Verify |
|:----------|:---------|:--------------|
| Models | Unit | Field defaults, status transitions, JSON serialization |
| Scanners | Unit | Known inputs → expected findings. Edge cases (empty files, syntax errors) |
| Exporters | Unit | DB records → markdown output matches expected format |
| Importers | Unit | Known markdown → correct DB records |
| Routes | Integration | HTTP status codes, template rendering, data display |
| CLI | Integration | Command output, side effects (file creation, DB changes) |

### Test Fixtures

```python
# conftest.py
import pytest
from app import create_app
from models import db as _db

@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db(app):
    return _db
```

### Scanner Test Pattern

```python
def test_coupling_scanner_finds_orphaned_template(tmp_path):
    """Scanner should detect templates not referenced by any route."""
    # Arrange: create a template with no route reference
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "orphan.html").write_text("<h1>Orphan</h1>")

    routes = tmp_path / "routes"
    routes.mkdir()
    (routes / "main.py").write_text("# no render_template calls")

    config = {"project_root": str(tmp_path), "paths": {"routes": "routes/", "templates": "templates/"}}

    # Act
    scanner = CouplingAuditScanner()
    result = scanner.scan(config)

    # Assert
    assert len(result.findings) == 1
    assert result.findings[0].severity == "warning"
    assert "orphan.html" in result.findings[0].message
```

---

## Git Workflow

### Branch Strategy

Linear development on `main` for now (single developer). Feature branches for multi-session work:

```bash
git checkout -b feature/coupling-scanner
# ... work ...
git checkout main
git merge feature/coupling-scanner
git branch -d feature/coupling-scanner
```

### Commit Messages

Use conventional commit format:

```
feat: add coupling audit scanner
fix: handle SyntaxError in AST parser
docs: add scanner specs documentation
refactor: extract base scanner protocol
test: add coupling scanner edge case tests
chore: update requirements.txt
```

### Pre-Commit Checks

Before committing:
```bash
black --check .
flake8 .
python -m pytest
```

---

## CLI Design Principles

1. **Consistent `--project` flag** across all commands
2. **JSON output option** (`--format json`) for all commands that display data
3. **Rich terminal output** by default (tables, colors, progress bars)
4. **Exit codes:** 0 = success, 1 = error, 2 = findings found (for CI integration)
5. **`--help`** always available and descriptive
