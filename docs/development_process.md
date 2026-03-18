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
```

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
├── test_scanners.py         # Scanner output correctness
├── test_exporters.py        # Export format fidelity
├── test_importers.py        # Import parsing accuracy
├── test_routes.py           # Web UI routes (status codes, templates)
└── test_cli.py              # CLI command behavior
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
