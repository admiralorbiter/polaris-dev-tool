# Config Schema

> Project YAML configuration specification with annotated examples.

**Last Updated:** March 2026

---

## Overview

Each target project gets a YAML file in `projects/`. The config tells DevTools where to find code, what patterns to look for, and which docs to manage.

---

## Full Annotated Schema

```yaml
# projects/vms.yaml
# ──────────────────────────────────────────────────────────────────

# IDENTITY
# ────────
project_name: "Polaris VMS"         # Human-readable display name
project_key: "vms"                  # Machine key (used in DB, CLI, URLs)
project_root: "c:/Users/admir/Github/VMS"  # Absolute path to repo root

# CODE PATHS
# ──────────
# Relative to project_root. Used by scanners to locate code.
paths:
  routes: "routes/"
  templates: "templates/"
  static: "static/"
  services: "services/"
  models: "models/"
  tests: "tests/"
  docs: "documentation/content/"
  scripts: "scripts/"

# CONVENTIONS
# ───────────
# Project-specific patterns that scanners use for analysis.
conventions:
  # Auth decorators the security scanner checks for.
  # Routes without one of these (and not in intentionally_public_routes)
  # are flagged as unprotected.
  auth_decorators:
    - "login_required"
    - "admin_required"
    - "global_users_only"
    - "global_admin_required"
    - "security_level_required"
    - "require_tenant_admin"

  # Routes that are intentionally public (no auth required).
  # Listed as blueprint.function_name format.
  intentionally_public_routes:
    - "auth.login"
    - "auth.magic_link_request"
    - "events.public_events"
    - "events.event_detail"
    - "district_api.get_events"

  # Function names used for template rendering (coupling scanner).
  template_render_function: "render_template"
  url_for_function: "url_for"

# MANAGED DOCS
# ─────────────
# Docs that DevTools owns. DB is the source of truth.
# The exporter writes to these paths (relative to project_root).
managed_docs:
  tech_debt:
    path: "documentation/content/developer/tech_debt.md"
    model: "WorkItem"                # Which DB model backs this doc
    format: "tech_debt_v1"           # Which exporter template to use
  status_tracker:
    path: "documentation/content/developer/development_status_tracker.md"
    model: "Feature"
    format: "status_tracker_v1"

# WATCHED DOCS
# ─────────────
# Docs DevTools checks for freshness (reads, never writes).
# Each entry maps a doc to the code paths it should track.
watched_docs:
  - doc: "documentation/content/developer/api_reference.md"
    watches:
      - "routes/api/"
      - "routes/district/api.py"
    priority: "high"

  - doc: "documentation/content/operations/smoke_tests.md"
    watches:
      - "tests/smoke/"
      - "tests/integration/"
    priority: "high"

  - doc: "documentation/content/operations/deployment.md"
    watches:
      - "config/"
      - "app.py"
    priority: "critical"

  - doc: "documentation/content/operations/runbook.md"
    watches:
      - "scripts/"
      - "config/"
    priority: "critical"

  - doc: "documentation/content/operations/import_playbook.md"
    watches:
      - "routes/salesforce/"
      - "services/salesforce/"
    priority: "high"

  - doc: "documentation/content/developer/cli_reference.md"
    watches:
      - "scripts/"
      - "cli.py"
    priority: "medium"

# Freshness urgency weights. Higher = more prominent in briefings.
freshness_weights:
  critical: 3.0       # Deployment, runbook
  high: 2.0           # API docs, import playbook
  medium: 1.0          # CLI reference, developer guides
  low: 0.5            # Internal notes

# EXISTING TOOLS
# ───────────────
# Tools already in the project that DevTools can invoke.
# Paths relative to project_root.
existing_tools:
  link_validator: "documentation/validate_links.py"
  test_runner: "run_tests.py"
```

---

## Minimal Config (New Project)

For a new project, the minimum required config:

```yaml
# projects/my_project.yaml
project_name: "My Project"
project_key: "my_project"
project_root: "c:/Users/admir/Github/my-project"

paths:
  routes: "routes/"
  templates: "templates/"
  models: "models/"
  tests: "tests/"

conventions:
  auth_decorators:
    - "login_required"
  intentionally_public_routes: []
  template_render_function: "render_template"
  url_for_function: "url_for"
```

All other sections (`managed_docs`, `watched_docs`, `existing_tools`, `freshness_weights`) are optional and default to empty.

---

## Validation Rules

On startup, DevTools validates each project config:

| Rule | Error Level |
|:-----|:-----------|
| `project_root` must exist as a directory | Fatal |
| `project_key` must be unique across all configs | Fatal |
| `paths.*` must exist relative to `project_root` | Warning (logged, scanner skips) |
| `managed_docs.*.path` parent directory must exist | Warning |
| `watched_docs.*.doc` must exist | Warning |
| `existing_tools.*` must exist | Info |
| `conventions.auth_decorators` should not be empty | Info |

---

## Config Loading

The config loader reads all `.yaml` files from `projects/` at startup:

```python
from pathlib import Path
import yaml

def load_project_configs() -> dict[str, dict]:
    configs = {}
    for yaml_file in Path("projects").glob("*.yaml"):
        with open(yaml_file) as f:
            config = yaml.safe_load(f)
        key = config["project_key"]
        config["_config_path"] = str(yaml_file)
        configs[key] = config
    return configs
```
