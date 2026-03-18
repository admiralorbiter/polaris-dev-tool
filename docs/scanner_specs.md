# Scanner Specifications

> Inputs, outputs, severity rules, and implementation notes for each scanner.

**Last Updated:** March 2026

---

## Scanner Registry

| Scanner | Key | Phase | Priority |
|:--------|:----|:------|:---------|
| [Coupling Audit](#coupling-audit) | `coupling` | 2 | Core |
| [Security Audit](#security-audit) | `security` | 2 | Core |
| [Tech Debt Parser](#tech-debt-parser) | `tech_debt` | 2 | Core |
| [Doc Freshness](#doc-freshness) | `freshness` | 3 | Core |
| [Impact Analyzer](#impact-analyzer) | `impact` | 4 | Core |
| [Obsolescence](#obsolescence) | `obsolescence` | 5 | Extended |
| [Script Import Validator](#script-import-validator) | `script_imports` | 5 | Extended |
| [Test-FR Coverage Mapper](#test-fr-coverage-mapper) | `test_coverage` | 5 | Extended |
| [Config Drift Detector](#config-drift-detector) | `config_drift` | 5 | Extended |
| [Migration Health Check](#migration-health-check) | `migration` | 5 | Extended |

---

## Coupling Audit

**Purpose:** Detect broken references between routes, templates, JS, and CSS.

### Checks

| Check | How | Severity |
|:------|:----|:---------|
| Route renders template that doesn't exist | AST parse for `render_template("X")`, verify `X` exists in `templates/` | 🔴 Critical |
| Template uses `url_for("X")` for non-existent route | Regex scan templates for `url_for`, check against registered routes | 🔴 Critical |
| Orphaned templates (no route references them) | Cross-reference all templates against all `render_template` calls | 🟡 Warning |
| Template includes CSS/JS that doesn't exist in `static/` | Regex scan for `href=` / `src=` pointing to `static/` | 🟡 Warning |
| Route defined but no template renders it (API-only OK) | Check routes without `render_template` that return HTML | 🔵 Info |

### Config Used

- `paths.routes` — where to find Python route files
- `paths.templates` — where to find template files
- `paths.static` — where to find static assets
- `conventions.template_render_function` — function name to scan for
- `conventions.url_for_function` — function name to scan for

### Output Example

```json
{
  "findings": [
    {
      "file": "routes/reports/recruitment.py",
      "line": 142,
      "message": "render_template('reports/old_recruitment.html') — template does not exist",
      "severity": "critical",
      "scanner": "coupling",
      "details": {"expected_template": "templates/reports/old_recruitment.html"}
    }
  ],
  "scanned_files": 110,
  "errors": [],
  "duration_ms": 450
}
```

---

## Security Audit

**Purpose:** Find routes missing authentication decorators.

### Checks

| Check | How | Severity |
|:------|:----|:---------|
| Route missing auth decorator | AST parse: check if function has any decorator from `conventions.auth_decorators` | 🔴 Critical |
| Auth decorator not in config | Grep for `@*_required` patterns not listed in `conventions.auth_decorators` | 🟡 Warning |
| Intentionally public route not in allowlist | Cross-reference `intentionally_public_routes` with actual public routes | 🔵 Info |

### Config Used

- `conventions.auth_decorators` — list of recognized auth decorators
- `conventions.intentionally_public_routes` — routes that should be public

### Implementation Notes

The AST parser walks each route file, finds functions decorated with `@bp.route(...)` or `@app.route(...)`, then checks if any of the remaining decorators match the `auth_decorators` list.

```python
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        has_route = any(is_route_decorator(d) for d in node.decorator_list)
        has_auth = any(is_auth_decorator(d, auth_list) for d in node.decorator_list)
        if has_route and not has_auth:
            # Check if it's in the intentionally_public list
            endpoint = f"{blueprint_name}.{node.name}"
            if endpoint not in public_routes:
                findings.append(...)
```

---

## Tech Debt Parser

**Purpose:** Parse existing `tech_debt.md` into structured WorkItem records for initial import and ongoing sync.

### Parse Rules

| Pattern | Extracts |
|:--------|:---------|
| `## TD-XXX: Title` | `source_id`, `title` |
| `**Created:** YYYY-MM-DD` | `identified_date` |
| `**Resolved:** YYYY-MM-DD` | `completed_at` |
| `**Priority:** High` | `priority` |
| `**Category:** Architecture` | `category` tag |
| `**Status:** RESOLVED` | `status = "done"` |
| `✅ RESOLVED` in heading | `status = "done"`, `is_archived = True` |
| `### Proposed Fix` / `### Resolution` | `notes` / `resolution_summary` |
| Table rows in Priority Order | `priority` ranking |

### Severity

This scanner doesn't produce findings — it produces WorkItems. No severity classification needed.

---

## Doc Freshness

**Purpose:** Detect docs that are stale relative to the code they document.

### Algorithm

For each `watched_docs` entry:
1. Get doc's last modification date via `git log -1 --format=%aI -- <doc_path>`
2. Get count of commits to watched code paths since that date
3. Apply `freshness_weights` multiplier
4. Flag if weighted commit count exceeds threshold (default: 3)

### Severity

| Weighted Commits Since Doc Update | Severity |
|:----------------------------------|:---------|
| 10+ (critical priority docs) | 🔴 Critical |
| 5–9 | 🟡 Warning |
| 3–4 | 🔵 Info |
| 0–2 | Not reported |

---

## Impact Analyzer

**Purpose:** Answer "What breaks if I change this file?"

### Algorithm

1. Build a reverse dependency graph:
   - Python files: parse `import` and `from X import Y` statements
   - Templates: parse `{% extends %}`, `{% include %}`, `url_for`
   - Static files: parse `<link href>`, `<script src>`
2. Given a file path, return all direct and transitive dependents

### Output

```json
{
  "target": "models/event.py",
  "direct_dependents": [
    "routes/events/routes.py",
    "routes/salesforce/event_import.py",
    "services/virtual_computation_service.py"
  ],
  "transitive_dependents": [
    "routes/reports/virtual_session/computation.py",
    "templates/events/view.html"
  ],
  "test_files": [
    "tests/unit/test_event_model.py"
  ]
}
```

---

## Obsolescence

**Purpose:** Find deprecated stubs, dead code blocks, and orphaned files.

### Checks

| Check | How | Severity |
|:------|:----|:---------|
| `{% if False %}` blocks in templates | Regex scan | 🟡 Warning |
| Functions with `DEPRECATED` in docstring | AST parse | 🟡 Warning |
| Files in `deprecated/` or `archive/` directories | File system | 🔵 Info |
| Python files not imported by any other file | Reverse import graph | 🔵 Info |

---

## Script Import Validator

**Purpose:** Verify that standalone scripts in `scripts/` can resolve their imports.

### Algorithm

1. Parse each `.py` file in `scripts/`
2. Extract all `from routes.X import Y` and `from services.X import Y` statements
3. Verify that `Y` exists in module `X` via AST analysis (not by importing — maintains zero-coupling)
4. Flag any unresolvable imports

### Severity

| Finding | Severity |
|:--------|:---------|
| Import target does not exist | 🔴 Critical |
| Import target exists but symbol name doesn't match | 🟡 Warning |

---

## Test-FR Coverage Mapper

**Purpose:** Map test case references (TC-xxx) in the status tracker to actual test files.

### Algorithm

1. Parse `Feature` records for `test_cases` JSON
2. Grep `tests/` for each TC reference
3. Flag TCs that are referenced but have no test function
4. Flag test files with no corresponding FR reference

---

## Config Drift Detector

**Purpose:** Find auth decorators in code that aren't listed in the project YAML config.

### Algorithm

1. AST parse all route files for decorator names matching `@*_required` or `@*_only`
2. Compare against `conventions.auth_decorators`
3. Flag any decorator found in code but missing from config

---

## Migration Health Check

**Purpose:** Validate Alembic migration state.

### Checks

| Check | How | Severity |
|:------|:----|:---------|
| Multiple Alembic heads | `alembic heads` returns >1 | 🔴 Critical |
| Database not at HEAD | `alembic current` ≠ `alembic heads` | 🟡 Warning |
| Migration files without downgrade | Parse migration files for `def downgrade()` body | 🔵 Info |
