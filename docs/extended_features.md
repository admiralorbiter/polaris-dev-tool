# Extended Features

> Health scoring, route registry, AI context integration, and project management capabilities.

**Last Updated:** March 2026

---

## 1. Project Health Score

A single 0–100 number that answers: "How healthy is this project right now?"

> **Status:** Basic scan-based score (0–100, color-coded ring) shipped in Phase 2. Full 5-component weighted score shipped in Phase 3b. Health score history + sparklines shipped in Phase 4c.

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

## 2. Route Registry ✅

A live, searchable catalog of every route in the project — built as a byproduct of the coupling scanner's AST parsing.

> **Status:** Shipped in Phase 2. Dashboard table with filtering, CLI query, and file:line tooltips.

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

Auto-generates structured context packets from scan findings for AI assistants. Also supports a full project context document for broader conversations.

> **Status:** Scan-based context packets shipped in Phase 2 (CLI, API, UI copy buttons). Task-specific templates and live DB sections planned for Phase 5a.

### Shipped: Scan Context Packets ✅

Each finding generates a structured block with:
- **Problem** — severity + message
- **Location** — file, line, blueprint, function, URL, methods
- **Context** — scanner-specific explanation
- **Suggested Fix** — severity-specific remediation
- **Code Snippet** — source lines with `>>>` marker

Access methods:
```bash
# CLI — all scanners to console
python cli.py context -p vms

# CLI — specific scanner to file
python cli.py context -p vms -s security --output ai_context.md

# CLI — copy to clipboard
python cli.py context -p vms --copy
```

UI: "📋 Copy AI Context" button on scan detail pages + per-finding copy buttons.

API: `GET /scans/<scanner>/context` returns `{text: ...}` JSON.

### Future: Full Context Generator (Phase 4)

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

## 5. Work Discovery & Prioritization

Answer the question: *"What should I work on today?"* with initiative grouping, session focus, and data-driven scoring.

> **Status:** ✅ All 3 parts shipped. Initiative Tags, Session Goal Picker, Smart Priority Scoring.

### 5A. Initiatives & Tags

An **Initiative** groups related work items under a thematic umbrella (e.g., "Architecture Hardening", "Email System", "MySQL Migration"):

```python
class Initiative(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)     # "Architecture Hardening"
    slug = db.Column(db.String(50), unique=True)          # "arch-hardening"
    description = db.Column(db.Text)                      # Goal, scope, context
    target_date = db.Column(db.Date)                      # Target completion
    created_at = db.Column(db.DateTime)
    # WorkItem.initiative_id → FK back to this
```

**Features:**

- **Initiatives list page** — all initiatives with progress bars (X/Y items done, % complete)
- **Initiative detail page** — linked work items, scan findings for related files, linked features
- **Work Board filter** — dropdown to filter by initiative
- **Work item form** — searchable initiative selector (same autocomplete pattern as feature picker)
- **Auto-seed** — create "Architecture Hardening" initiative, link existing TD-009, TD-016, TD-022, TD-041

### 5B. Session Goal Picker

When starting a session, choose a **focus initiative** (or enter free-text):

```
▶ Start Session
  What are you focused on today?
  ○ Architecture Hardening    (3 open items, 24 coupling findings)
  ○ Email System              (22 pending features)
  ○ Test Coverage             (9/26 services done)
  ○ Bug Fixes                 (1 open bug)
  ○ Custom: [____________]
```

**Effect on session:**

| Component | Without Goal | With Goal |
|:----------|:-------------|:----------|
| Briefing work items | All in-progress | Only items in selected initiative |
| Scan findings | All critical | Only findings for files in initiative's code_paths |
| Dashboard badge | "Session 1 active" | "Session 1 — Architecture Hardening" |
| Receipt | All changes | Highlights changes in initiative's scope |

**Storage:** `SessionLog.goal` (text), `SessionLog.initiative_id` (FK, nullable)

### 5C. Smart Priority Scoring

Auto-rank items by a weighted formula that considers multiple signals:

```
Score = (priority_weight × 3)
      + (age_days × 0.1)
      + (blocking_count × 5)
      + (scan_finding_overlap × 2)
      + (initiative_alignment × 3)
```

| Input | How It's Calculated |
|:------|:-------------------|
| `priority_weight` | critical=4, high=3, medium=2, low=1 |
| `age_days` | Days since `created_at` |
| `blocking_count` | How many items list this one as a dependency |
| `scan_finding_overlap` | Scan findings in the item's `code_paths` |
| `initiative_alignment` | +3 if item matches current session's initiative |

**UI: "Suggested Next" panel on Work Board:**

```
📊 Suggested Next
1. TD-009 — Centralize Transaction Management      [Score: 18.2]
   high priority • 12 days old • blocks MySQL migration

2. TD-022 — Service Test Coverage                  [Score: 14.6]
   medium priority • in-progress (9/26) • momentum bonus
```

One-click **"Start Working"** → sets `status = in_progress`, links to current session.

---

## Phase Integration

These features slot into the existing phases:

| Feature | Phase | Status |
|:--------|:------|:-------|
| Route registry | 2 | ✅ Shipped |
| Health score (basic scan-based) | 2 | ✅ Shipped |
| AI context packets (scan findings) | 2 | ✅ Shipped |
| Health score (5-component weighted) | 3b | ✅ Shipped |
| Bug/feature quick-capture CLI | 3a | ✅ Shipped |
| Scan drill-down + finding→WorkItem | 4a | ✅ Shipped |
| Feature review queue | 4a | ✅ Shipped |
| Commit message generator | 4b | ✅ Shipped |
| Source ID auto-generation | 4d+ | ✅ Shipped |
| Feature linking (WorkItem→Feature) | 4d+ | ✅ Shipped |
| AI context (task templates, live DB) | 5a | Planned |
| Initiative tags & grouping | 5c-Part 1 | ✅ Shipped |
| Session goal picker | 5c-Part 2 | ✅ Shipped |
| Smart priority scoring | 5c-Part 3 | ✅ Shipped |
| Sprint planning view | 6 | Planned |
| Milestone tracking | 6 | Planned |
| Velocity tracking | 6 | Planned |
| Data health sub-score | 6 | Planned |
| Quarterly review generator | 6 | Planned |
