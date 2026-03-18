# Architecture

> Source-of-truth model, ownership boundaries, export mechanics, and scanner protocol.

**Last Updated:** March 2026

---

## System Overview

Polaris DevTools is a **source-of-truth + export** system. Structured development data (tech debt, features, work items) lives in a SQLite database. DevTools renders this data as markdown and exports it to target project repos.

```
┌─────────────────────────────────────────────────────────┐
│  Polaris DevTools (localhost:5001)                       │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐    │
│  │ Scanners │   │   CLI    │   │   Web Dashboard  │    │
│  └────┬─────┘   └────┬─────┘   └────────┬─────────┘    │
│       │              │                   │              │
│       ▼              ▼                   ▼              │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Core Services                        │   │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────────┐ │   │
│  │  │ Importers│ │ Exporters │ │ Session Manager  │ │   │
│  │  └──────────┘ └───────────┘ └──────────────────┘ │   │
│  └───────────────────────┬──────────────────────────┘   │
│                          │                              │
│  ┌───────────────────────▼──────────────────────────┐   │
│  │           SQLite Database (WAL mode)              │   │
│  │  WorkItem │ Feature │ ScanResult │ SessionLog     │   │
│  └───────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────┼──────────┐
          │ read     │ export   │ auto-stage
          ▼          ▼          ▼
┌─────────────────────────────────────────┐
│   Target Project (e.g., VMS)            │
│   ├── routes/         ◄── scanned       │
│   ├── templates/      ◄── scanned       │
│   ├── models/         ◄── scanned       │
│   ├── services/       ◄── scanned       │
│   ├── tests/          ◄── scanned       │
│   ├── scripts/        ◄── scanned       │
│   └── documentation/                    │
│       └── content/developer/            │
│           ├── tech_debt.md    ◄── exported
│           └── dev_status.md   ◄── exported
└─────────────────────────────────────────┘
```

---

## Ownership Model

### What DevTools Owns

DevTools is the **single writer** for these assets. The database is the source of truth; markdown files are rendered exports.

| Asset | DB Table | Export Target |
|:------|:---------|:-------------|
| Tech debt items (TD-xxx) | `WorkItem` | `documentation/content/developer/tech_debt.md` |
| Feature/FR tracking | `Feature` | `documentation/content/developer/development_status_tracker.md` |
| Work board items | `WorkItem` | N/A (internal to DevTools) |
| Scan results | `ScanResult` | N/A (internal to DevTools) |
| Session logs | `SessionLog` | N/A (internal to DevTools) |

### What DevTools Reads

DevTools scans these assets but **never modifies** them:

| Asset | How Scanned |
|:------|:-----------|
| Python source (routes, models, services) | AST parsing, regex, file system |
| Templates (HTML/Jinja) | Regex for `render_template`, `url_for` |
| Tests | File system correlation with code |
| Git history | `gitpython` commands |
| Operational docs (runbook, deployment) | File modification timestamps via git |
| Requirements docs | Parsed for FR cross-referencing |
| Existing tools (`validate_links.py`) | Invoked as subprocess |

### What DevTools Never Touches

- Python source code
- Test files
- HTML/Jinja templates
- Config files (`.env`, `config.py`)
- Alembic migration files
- Requirements specification documents

---

## Export Engine

### Lifecycle

1. **Record changes** in the database via UI or CLI
2. **Dirty flag** is set on modification (`WorkItem.updated_at > last_export_at`)
3. **Export trigger** fires (manual `cli.py export` or auto on `cli.py receipt`)
4. **Renderer** converts DB records to markdown using a template
5. **Writer** outputs the file to the configured path in the target project
6. **Auto-stage** runs `git add <file>` on the exported file
7. **User commits** the staged changes with their next `git commit`

### Export Header

All exported files include this header to prevent direct editing:

```markdown
<!-- ┌─────────────────────────────────────────────────────────────┐ -->
<!-- │ AUTO-GENERATED by Polaris DevTools                         │ -->
<!-- │ Source of truth: DevTools DB (localhost:5001)               │ -->
<!-- │ Last exported: 2026-03-18 14:05:00                         │ -->
<!-- │ Edit via DevTools UI or CLI, not directly in this file.    │ -->
<!-- └─────────────────────────────────────────────────────────────┘ -->
```

### Dirty-Flag Strategy

Each managed doc tracks its last export timestamp. On export, only dirty records are re-rendered. A doc is dirty if any of its backing records have `updated_at > last_export_at`.

---

## Scanner Protocol

Scanners are pure Python classes that implement a minimal interface:

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class ScanFinding:
    file: str
    line: int | None
    message: str
    severity: str        # "critical", "warning", "info"
    scanner: str         # e.g., "coupling"
    details: dict | None # scanner-specific data

@dataclass
class ScanOutput:
    findings: list[ScanFinding]
    scanned_files: int
    errors: list[str]    # files that failed to parse
    duration_ms: int

class Scanner(Protocol):
    name: str
    description: str
    version: str

    def scan(self, project_config: dict) -> ScanOutput: ...
```

### Fail-Open Principle

Scanners **must not crash** on bad input. Every file operation wraps in error handling:

```python
try:
    tree = ast.parse(source)
except SyntaxError as e:
    errors.append(f"{filepath}: {e}")
    continue  # Skip file, don't abort scan
```

Handled errors:
- `SyntaxError` — Python file has syntax errors (common during active development)
- `UnicodeDecodeError` — binary file mistakenly included
- `FileNotFoundError` — file deleted between directory listing and read
- `PermissionError` — OS-level access denied

---

## Project Configuration

DevTools discovers target projects via YAML files in `projects/`. See [Config Schema](config_schema.md) for the full specification.

Key architectural constraints:
- One YAML file per project
- Paths are relative to `project_root`
- `managed_docs` declares which files DevTools exports to
- `watched_docs` declares which files DevTools checks for freshness
- `conventions` declares project-specific patterns (auth decorators, etc.)

---

## Zero-Coupling Guarantee

DevTools **never** does:
```python
# ❌ NEVER — no import coupling
from routes.virtual import process_pathful_data
from models.event import Event
```

DevTools **always** does:
```python
# ✅ ALWAYS — filesystem scanning
import ast
with open(filepath) as f:
    tree = ast.parse(f.read())

# ✅ ALWAYS — git via gitpython
repo = git.Repo(project_root)
diffs = repo.head.commit.diff('HEAD~1')
```

This means:
- DevTools can't break your project
- Your project never depends on DevTools
- DevTools works with any project that follows common Python/Flask patterns
- Adding a new project = adding a new YAML config file
