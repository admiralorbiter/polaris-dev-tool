# Extended Features

> Health scoring, route registry, AI context integration, and project management capabilities.

**Last Updated:** March 2026

---

## 1. Project Health Score

A single 0–100 number that answers: "How healthy is this project right now?"

### Score Composition

| Component | Weight | 100 Points If... | 0 Points If... |
|:----------|:-------|:-----------------|:---------------|
| **Scan Findings** | 30% | Zero critical/warning findings | 10+ critical findings |
| **Doc Freshness** | 20% | All watched docs current | 3+ docs with critical staleness |
| **Tech Debt Load** | 20% | Zero active high-priority items | 10+ active high-priority items |
| **Test Activity** | 15% | Tests changed with code in last 5 sessions | Tests never changed |
| **Work Board Flow** | 15% | Items moving through statuses | All items stuck in backlog |

### Display

- **Dashboard:** Large circular gauge on the landing page, color-coded (green 80+, yellow 50–79, red <50)
- **CLI:** Single line in briefing: `Health: 72/100 (↑3 from last session)`
- **Trend:** Sparkline showing last 10 sessions

### Data Health Sub-Score

For projects with data pipelines (like VMS), an additional **Data Health** score:

| Component | What It Checks |
|:----------|:--------------|
| Import freshness | Last successful import timestamp vs schedule |
| Sync errors | Count of recent sync failures |
| Data quality flags | Open flags from data quality dashboard |
| Schema drift | Pending migrations, multiple Alembic heads |

This surfaces as a secondary score: `Data Health: 85/100`

---

## 2. Route Registry

A live, searchable catalog of every route in the project — built as a byproduct of the coupling scanner's AST parsing.

### What It Captures

| Field | Source |
|:------|:-------|
| Blueprint name | File path → blueprint inference |
| Route URL pattern | `@bp.route("/path")` decorator arg |
| HTTP methods | `methods=["GET", "POST"]` |
| Function name | AST function def |
| Auth decorator | Which decorator protects it |
| Template rendered | `render_template("X")` call |
| File + line number | AST node location |
| Last modified | `git log -1` on the file |

### Features

- **Searchable table** in the dashboard (filter by blueprint, auth status, HTTP method)
- **CLI query:** `python cli.py routes --project vms --filter /district/`
- **Unprotected route highlighting** (no auth decorator, not in allowlist)
- **Dead route detection** (route exists but template references zero `url_for` calls to it)
- **API-only vs HTML routes** (has `render_template` or returns `jsonify`)

### Storage

Routes are stored in `ScanResult` with `scanner="route_registry"`. Re-scanned on each full scan. The dashboard reads from the latest scan result.

---

## 3. AI Context Generator

Auto-generates a project context document that can be pasted into AI conversations. Expands on the existing `ai_collab_guide.md` pattern but with **live data** from DevTools.

### Generated Context Sections

The generator produces a markdown document with these sections:

#### Static (from project config + AI collab guide)
- Tech stack summary
- Key architecture patterns
- Conventions (auth decorators, naming, etc.)
- Safety rules (destructive action warnings, PII rules)

#### Live (from DevTools DB)
- **Active work items:** Current in-progress items with context
- **Recent changes:** Last 3 session receipts (summarized)
- **Critical findings:** Any critical scan findings
- **Hot files:** Files changed most frequently in last 5 sessions
- **Tech debt context:** Top 3 active high-priority debt items

#### Task-Specific Templates
Based on the `ai_collab_guide.md` common task prompts:

| Template | What DevTools Adds |
|:---------|:------------------|
| **Sprint Planning** | Pre-populated with current backlog, priorities, and dependencies from WorkItem table |
| **Retro** | Pre-populated with completed items, new debt items, and doc drift from last N sessions |
| **Code Review** | Pre-populated with active tech debt IDs and recent scan findings for the changed files |
| **Debugging** | Pre-populated with relevant file dependencies from impact analyzer |

### Commands

```bash
# Generate full context (copy to clipboard)
python cli.py context --project vms

# Generate task-specific context
python cli.py context --project vms --template sprint-planning
python cli.py context --project vms --template retro
python cli.py context --project vms --template code-review --files routes/virtual/usage.py

# Regenerate and copy
python cli.py context --project vms --copy
```

### Dashboard

A "Copy AI Context" button on the dashboard that generates the latest context and copies to clipboard.

---

## 4. Project Management Features

### 4A. Sprint Planning View

A dedicated view for planning work:

- **Backlog triage:** Drag items between priority levels
- **Sprint board:** Select items for "this sprint" (1–2 week window)
- **Effort totals:** Sum of effort estimates (S=1, M=2, L=4, XL=8 points)
- **Dependency graph:** Visual view of blocked-by relationships
- **Auto-suggest:** Based on priority, age, and dependency readiness, suggest "top 5 items to work on next"

### 4B. Bug & Feature Reports

Structured templates for capturing bugs and feature requests:

**Bug Report model** (extends WorkItem):
```
category: "bug"
extra fields in notes JSON:
  - steps_to_reproduce
  - expected_behavior
  - actual_behavior  
  - environment (browser, OS, etc.)
  - screenshot_path
```

**Feature Request model** (extends WorkItem):
```
category: "feature"
extra fields in notes JSON:
  - user_story (As a ___, I want ___, so that ___)
  - acceptance_criteria (checklist)
  - requested_by
  - impact_assessment
```

CLI quick-capture:
```bash
# Quick bug report
python cli.py bug --project vms --title "District export returns 500" --priority high

# Quick feature request
python cli.py feature-request --project vms --title "Bulk teacher import via CSV"
```

### 4C. Long-Term Planning

**Milestone Tracking:**
- Group WorkItems and Features under milestones (e.g., "Email System v1", "MySQL Migration")
- Track milestone completion percentage
- Estimated completion date based on velocity (items completed per session)

**Velocity Tracking:**
- Items completed per session (from session logs)
- Average session duration
- Completion rate by category (bugs vs features vs debt)
- Projected dates for milestone completion

**Quarterly Review Generator:**
- Auto-generate a summary of what shipped in the last quarter
- Tech debt resolved vs created
- Feature adoption rates (from 90-day reviews)
- Health score trend over the quarter

### 4D. Commit Message Generator

The receipt already knows the 9-layer changes. Auto-generate a commit message:

```bash
python cli.py receipt --project vms

# After receipt displays, it offers:
# 
# Suggested commit message:
# ─────────────────────────
# feat(district): add /district/export route
# 
# - 7 files changed, 2 new
# - New route: GET /district/export (admin_required)
# - Models: event.py (2 fields added)
# - Tests: 3 new tests
# - Services: session_status_service.py updated
# 
# Refs: TD-046
# ─────────────────────────
# [C]opy to clipboard  [E]dit  [S]kip
```

---

## Phase Integration

These features slot into the existing phases:

| Feature | Phase | Rationale |
|:--------|:------|:----------|
| Route registry | 2 | Byproduct of coupling scanner AST parsing |
| Health score (basic) | 3 | Needs scan results + work items |
| Bug/feature quick-capture CLI | 3 | Extends WorkItem CRUD |
| Commit message generator | 4 | Part of receipt workflow |
| AI context generator | 4 | Needs session logs + scan results |
| Sprint planning view | 5 | Dashboard feature, needs all data |
| Milestone tracking | 5 | Aggregation over work items |
| Velocity tracking | 5 | Aggregation over session logs |
| Data health sub-score | 5 | Project-specific, needs custom config |
| Quarterly review generator | 5 | Aggregation feature |
