# Roadmap

> Build phases with acceptance criteria and dependencies.
>
> See also: [Extended Features](extended_features.md) for detailed specs on health score, route registry, AI context, and PM features.

**Last Updated:** March 2026

---

## Phase Overview

| Phase | Name | Key Deliverable | Est. Sessions | Status |
|:------|:-----|:----------------|:-------------|:-------|
| 0 | Documentation | Project docs | 1 | ✅ |
| 1 | Foundation + Export Engine | Running app with DB, export, basic dashboard | 2–3 | ✅ |
| 2 | Scanners + Import | Coupling/security scanners, tech debt import | 3–4 | ✅ |
| 3a | CRUD + Imports | Work board, feature lifecycle, status tracker import | 1–2 | ✅ |
| 3b | Infrastructure | Doc freshness, health score, status tracker export | 1–2 | ✅ |
| 4a | Actionability | Scan drill-down, finding→WorkItem, review queue | 1–2 | ✅ |
| 4b | Session Loop | Briefing + receipt + 9-layer matrix + post-hooks | 1–2 | ✅ |
| 4c | Time & Trends | Date filters, health score history, sparklines | 1 | Planned |
| 5a | AI Context v2 | Task templates, live DB context, full project context | 1 | Planned |
| 5b | Extended Scanners | Impact analyzer + 5 more scanners | 2–3 | Planned |
| 6 | PM & Polish | Sprint planning, milestones, velocity, quarterly review | 2–3 | Planned |

---

## Phase 0: Documentation ✅

> Foundational project documentation.

- [x] Kickoff document (spec + high-level design)
- [x] Architecture doc (ownership, export, scanner protocol)
- [x] Data models doc (4 models, field specs)
- [x] Config schema doc (annotated YAML)
- [x] Session workflow doc (briefing, 9-layer matrix)
- [x] Scanner specs doc (all 10 scanners)
- [x] Roadmap doc (this file)
- [x] Development process doc (how we build this tool)

**Acceptance:** All docs committed. Ready to start coding.

---

## Phase 1: Foundation + Export Engine ✅

### Deliverables

- [x] Flask app scaffold (`app.py`, `config.py`)
- [x] All 4 database models (`models.py`)
- [x] SQLite with WAL mode enabled
- [x] Alembic migration setup + initial migration
- [x] VMS project config YAML (`projects/vms.yaml`)
- [x] Config loader with validation
- [x] Base template with dark theme + navigation shell
- [x] Dashboard page (placeholder panels)
- [x] Health-check endpoint (`GET /api/health`)
- [x] Export engine base:
  - [x] Markdown renderer interface
  - [x] Dirty-flag tracking (`last_export_at` per managed doc)
  - [x] Git auto-stage on export
- [x] CLI scaffolding (Click groups: `scan`, `briefing`, `receipt`, `export`, `import`)
- [x] `.env` support via `python-dotenv`
- [x] `.gitignore`
- [x] `requirements.txt`
- [x] Basic test setup (`conftest.py`, model tests)

### Acceptance Criteria

1. `python app.py` starts the server on `localhost:5001`
2. `GET /api/health` returns `{"status": "ok"}`
3. Dashboard loads with placeholder panels
4. `python cli.py export --project vms --target tech_debt` writes a file (even if empty template)
5. Database tables exist and can be queried
6. All tests pass

### Dependencies

- None (first phase)

---

## Phase 2: Scanners + Tech Debt Import ✅

### Deliverables

- [x] Scanner protocol (`scanners/base.py`)
- [x] Coupling audit scanner (`scanners/coupling_audit.py`)
  - [x] Route → template sync check
  - [x] Template → route sync (`url_for` validation)
  - [x] Orphaned templates detection
- [x] Security audit scanner (`scanners/security_audit.py`)
  - [x] Auth decorator coverage check
  - [x] Intentionally-public route validation
- [x] CLI: `python cli.py scan --project vms --scanner coupling`
- [x] CLI: `python cli.py scan --project vms --scanner security`
- [x] CLI: `python cli.py scan --project vms --scanner all`
- [x] Dashboard: scan results panel with severity badges
- [x] Tech debt importer (`importers/tech_debt_importer.py`)
  - [x] Parse VMS `tech_debt.md` (47 items — IDs 42–45 are intentionally skipped)
  - [x] Create WorkItems with `is_archived=True` for resolved items
  - [x] Preserve source_id, priority, dates, resolution summaries
- [x] Tech debt exporter (`exporters/tech_debt_exporter.py`)
  - [x] Render WorkItems → markdown matching VMS format
  - [x] Include active items, priority table, and resolved archive
- [x] **Route registry** (byproduct of coupling scanner AST parsing)
  - [x] Capture: blueprint, URL, methods, auth, template, file+line
  - [x] Searchable/filterable table in dashboard
  - [x] CLI: `python cli.py routes --project vms`
- [x] CLI: `python cli.py import tech-debt --project vms`
- [x] CLI: `python cli.py export tech-debt --project vms`
- [x] Scanner tests + edge cases (62 tests → 76 tests)
- [x] Importer/exporter tests
- [x] **AI Context Packet** (pulled forward from Phase 4)
  - [x] Context formatter utility (`utils/context_formatter.py`)
  - [x] Scanner-specific context templates with fix guidance
  - [x] Source code snippet extraction with `>>>` line marker
  - [x] CLI: `python cli.py context -p vms -s security [--output file | --copy]`
  - [x] API: `GET /scans/<scanner>/context` returns JSON
  - [x] UI: "📋 Copy AI Context" button + per-finding copy buttons
  - [x] Context formatter tests (14 tests)
- [x] **Dashboard QOL** (UI feedback session)
  - [x] Health score ring (computed from scan findings, color-coded)
  - [x] Import timestamp on Work Items card
  - [x] Findings grouped by file on scan detail page
  - [x] Scanner errors in collapsible section
  - [x] File:Line column tooltip on routes table

### Acceptance Criteria

1. ✅ Coupling scanner finds orphaned templates in VMS
2. ✅ Security scanner identifies routes correctly as protected/unprotected
3. ✅ Import creates 47 WorkItem records from `tech_debt.md`
4. ✅ Export renders a `tech_debt.md` that is structurally equivalent to the original
5. ✅ Dashboard shows scan results with severity badges
6. ✅ Route registry displays all 173 VMS routes with auth status
7. ✅ AI context packets generate copy-paste-ready text with code snippets
8. ✅ All 76 tests pass, 0 lint errors

### Dependencies

- Phase 1 (app, models, CLI skeleton)

---

## Phase 3a: CRUD + Imports ✅

> **Scope:** Everything the user interacts with daily. Build, test, UI feedback, then move to 3b.

### Deliverables

- [x] WorkItem CRUD routes and UI
  - [x] Create, read, update, complete, archive
  - [x] Filter by status, priority, category
  - [x] Work board template (table view, archive toggle, priority sorting)
- [x] Feature CRUD routes and UI
  - [x] Create, read, update, ship
  - [x] Auto-set `next_review` on ship date
  - [x] Feature lifecycle template (status badges, 90-day countdown)
- [x] Status tracker importer (`importers/status_tracker_importer.py`)
  - [x] Parse VMS `development_status_tracker.md` (244 FRs across 10 domains)
  - [x] Map status symbols (✅/🔧/📋/🔮/➖), extract domain + test cases
- [x] Bug/feature quick-capture CLI
  - [x] `cli.py bug --project vms --title "..." --priority high`
  - [x] `cli.py feature-request --project vms --title "..."`
- [x] CRUD + importer tests (26 new tests → 106 total)
- [x] UI feedback + polish (markdown rendering, dashboard links, hover states)

### Acceptance Criteria

1. ✅ Work board displays all 47 imported tech debt items with filter/archive
2. ✅ Features display all 244 imported FRs with correct status symbols
3. ✅ Archiving a WorkItem removes it from the active board
4. ✅ `cli.py bug` and `cli.py feature-request` create correct WorkItem records
5. ✅ Status tracker import creates 244 Feature records from VMS
6. ✅ All 106 tests pass

### Dependencies

- Phase 2 (import/export infrastructure, scanner framework)

---

## Phase 3b: Exporters + Scanners + Health Score ✅

> **Scope:** Supporting infrastructure that makes the CRUD layer self-maintaining. Only start after 3a UI feedback.

### Deliverables

- [x] Status tracker exporter (`exporters/status_tracker_exporter.py`)
  - [x] Round-trip rendering: Features → VMS markdown format (357 lines, 244 features)
  - [x] Auto-computed summary table, status legend, domain sections
- [x] Doc freshness scanner (`scanners/doc_freshness.py`)
  - [x] Git log-based staleness detection (doc last-modified vs source last-modified)
  - [x] Uses `watched_docs` config with priority → severity mapping
  - [x] Found 4 critical + 3 warning stale docs in VMS
- [x] Export-on-receipt integration (`cli.py export sync`)
  - [x] Auto-export dirty managed docs based on last export vs record update
  - [x] Auto-stage exported files in git
- [x] **Project health score** (enhanced — 5-component weighted system)
  - [x] ~~Basic scan-based score (0–100, color-coded gauge on dashboard)~~ _(shipped in Phase 2)_
  - [x] Score engine: `utils/health_score.py` with 5 components (20% each):
    - Scan Health (100 − 10×criticals − 3×warnings)
    - Doc Freshness (based on stale doc findings)
    - Debt Load (based on active item count and priority)
    - Feature Coverage (implemented / total × 100)
    - Work Flow (completed_30d / backlog × 100)
  - [x] Dashboard component breakdown with color-coded progress bars
- [x] Exporter + scanner tests (24 new tests → 130 total)
- [x] UI polish: logo links to home, 5-panel single-row dashboard layout

### Acceptance Criteria

1. ✅ Status tracker export produces markdown structurally equivalent to VMS format
2. ✅ Doc freshness scanner correctly flags 7 stale docs
3. ✅ Health score reflects all 5 components with labeled breakdown
4. ✅ Export sync writes and stages updated files
5. ✅ All 130 tests pass

### Dependencies

- Phase 3a (CRUD + imports must be validated first)

---

## Phase 4a: Actionability ✅

> **Goal:** Close the observe→act loop. The tool already finds problems — now let the user *do* something about them.
>
> **Use case addressed:** All 3 daily workflows (Morning Check-In, Working Session, Weekly Review)

### Deliverables

- [x] **Scan drill-down from dashboard**
  - [x] Per-scanner cards on dashboard (Coupling, Security, Doc Freshness) with finding counts
  - [x] Click panel → navigate to `/scans` list
  - [x] Doc freshness findings visible in UI (finding count on dashboard, detail at `/scans/doc_freshness`)
- [x] **Finding → WorkItem pipeline**
  - [x] "🐛 Create Item" button on each scan finding
  - [x] Pre-populate title, priority (from severity), category ("review"), notes (finding detail)
  - [x] Severity→priority mapping: critical→high, warning→medium, info→low
- [x] **Feature review queue**
  - [x] Dashboard card: "N features due for review" (where `next_review ≤ today + 14 days`)
  - [x] Clickable → filtered feature list at `/features?review=due`
  - [x] Visual indicator on feature detail page (days until review, overdue badge) _(shipped in 3a)_
- [x] **Dashboard navigation polish**
  - [x] All stat panels clickable (Work Items, Features, Scans → respective list pages)
  - [x] Empty state improvements (Sessions panel → "Coming in Phase 4b")
  - [x] Dashboard grid: 3×2 layout with 6 panels
  - [x] Footer updated to "Phase 4a: Actionability"
- [x] Tests for 4a (18 new tests, 183 total, 86% coverage)

### Acceptance Criteria

1. ✅ Clicking a scan finding shows enough detail to understand *what* to fix
2. ✅ One-click path from finding → new WorkItem with pre-populated fields
3. ✅ Feature review queue surfaces features approaching their 90-day review
4. ✅ All dashboard panels are actionable (clickable or informative)
5. ✅ All tests pass (183/183)

### Dependencies

- Phase 3b (scan findings, health score, export sync)

---

## Phase 4b: Session Loop

> **Goal:** Automate the dev session bookends — what to know when you start, what happened when you stop.
>
> **Use case addressed:** Morning Check-In (briefing) and end-of-session (receipt)
>
> **Spec reference:** [Session Workflow](session_workflow.md) for the full 9-layer matrix definition

### Deliverables

- [x] **Pre-session briefing** (`cli.py briefing --project vms`)
  - [x] 6-point checklist:
    1. Git state (branch, dirty, ahead/behind)
    2. Critical scan findings (latest results)
    3. In-progress work items
    4. Upcoming feature reviews (next 14 days)
    5. Doc freshness alerts (stale docs)
    6. Managed doc status (dirty export count)
  - [x] Rich terminal output (via `rich`)
  - [x] Store briefing as JSON in `SessionLog.briefing_json`
  - [x] Record `commit_range_start` (current HEAD)
- [x] **Post-session receipt** (`cli.py receipt --project vms`)
  - [x] 9-layer change matrix (classify every file changed since briefing):
    1. Files Changed (`git diff --stat`)
    2. Routes Added/Modified (AST parse)
    3. Models Touched (file detection)
    4. Templates Changed (`.html` files)
    5. Tests Added/Modified (`tests/` files)
    6. Services Affected (`services/` files)
    7. Docs Updated (`documentation/` files) — **drift detection alert**
    8. Dependencies Changed (`requirements.txt`, `package.json`)
    9. Config Changes (`.env`, `config.py`, YAML)
  - [x] Layer 7 drift detection:
    - Code changed but managed docs not exported → alert
    - New routes added but API docs not updated → alert
    - Test files changed but smoke_tests.md stale → alert
  - [x] Persist receipt JSON in `SessionLog`
- [x] **Post-receipt automation**
  - [x] Auto-export dirty managed docs (hook into `export sync`)
  - [x] Auto-stage exported files in git
  - [x] Auto-create drift WorkItems for Layer 7 alerts
- [x] **Commit message generator**
  - [x] Auto-draft from receipt (summary line + body from 9-layer changes)
  - [x] Copy to clipboard option
  - [x] CLI: `[C]opy [E]dit [S]kip` prompt after receipt
- [x] **SessionLog model extension**
  - [x] Add fields: `briefing_json`, `receipt_json`, `commit_range_start`, `commit_range_end`, `files_changed`, `docs_exported`
- [x] **Dashboard: session history view**
  - [x] List of past sessions with date, duration, files changed, findings
  - [x] Session detail page with full receipt view
- [x] Tests for 4b (briefing generation, receipt classification, post-hooks)

### Acceptance Criteria

1. ✅ Briefing correctly reports git state, critical findings, and in-progress items
2. ✅ Receipt correctly classifies changes into 9 layers
3. ✅ Layer 7 drift detection flags undocumented changes
4. ✅ Post-receipt hooks export and stage files
5. ✅ Commit message generator produces sensible conventional commits
6. ✅ Session history is queryable from dashboard and CLI
7. ✅ All 225 tests pass (42 new Phase 4b tests)

### Dependencies

- Phase 4a (finding→WorkItem pipeline used by drift auto-creation)

---

## Phase 4c: Time & Trends

> **Goal:** Add the time dimension. Everything so far is point-in-time — now track how things change.
>
> **Use case addressed:** Weekly Review

### Deliverables

- [ ] **Health score history**
  - [ ] Record health score snapshot on each briefing/receipt
  - [ ] New model or JSON column: `HealthSnapshot(date, score, components_json)`
  - [ ] Dashboard sparkline: health score trend (last 10 data points)
- [ ] **Time-scoped work board**
  - [ ] "Completed this week" filter on work items
  - [ ] "Created this week" filter
  - [ ] Date range selector for custom views
- [ ] **Scan trend tracking**
  - [ ] Finding counts over time (critical/warning/info per scan run)
  - [ ] Dashboard mini-chart: findings trend
- [ ] Tests for 4c

### Acceptance Criteria

1. Health score sparkline shows a visible trend on the dashboard
2. Work board can filter by completion date range
3. Scan finding trend shows whether things are getting better or worse
4. All tests pass

### Dependencies

- Phase 4b (session logs provide the health snapshots)

---

## Phase 5a: AI Context v2

> **Goal:** Upgrade AI context generation from scan-only packets to full project context with task templates.
>
> **Spec reference:** [Extended Features § AI Context Generator](extended_features.md#3-ai-context-generator)

### Deliverables

- [ ] **Static context sections** (from project config)
  - [ ] Tech stack summary
  - [ ] Architecture patterns and conventions
  - [ ] Safety rules (destructive action warnings, PII rules)
- [ ] **Live context sections** (from DevTools DB)
  - [ ] Active work items (current in-progress with context)
  - [ ] Recent session receipts (last 3, summarized)
  - [ ] Critical scan findings
  - [ ] Hot files (most frequently changed in last 5 sessions)
  - [ ] Top 3 active high-priority debt items
- [ ] **Task-specific templates**
  - [ ] Sprint planning (backlog, priorities, dependencies from WorkItems)
  - [ ] Retro (completed items, new debt, doc drift from recent sessions)
  - [ ] Code review (active debt IDs, scan findings for changed files)
  - [ ] Debugging (file dependencies from impact analyzer, if available)
- [ ] CLI: `cli.py context --project vms --template sprint-planning`
- [ ] Dashboard: "Copy AI Context" button with template selector
- [ ] Tests for 5a

### Acceptance Criteria

1. Full context includes both static config and live DB data
2. Task-specific templates pre-populate with relevant project data
3. Context is copy-paste ready for AI assistants
4. All tests pass

### Dependencies

- Phase 4b (session logs provide "recent changes" data)

---

## Phase 5b: Extended Scanners

> **Goal:** Build out the remaining 6 scanners from the [Scanner Specs](scanner_specs.md).

### Deliverables

- [ ] **Impact analyzer** (`scanners/impact_analyzer.py`)
  - [ ] Reverse dependency graph (Python imports, template `extends`/`include`, static refs)
  - [ ] "What breaks if I change X?" query
  - [ ] CLI: `cli.py impact --project vms --file routes/events/routes.py`
- [ ] **Obsolescence scanner** (`scanners/obsolescence.py`)
  - [ ] `{% if False %}` blocks, `DEPRECATED` docstrings, files in `deprecated/` dirs
  - [ ] Orphaned Python files (not imported by any other file)
- [ ] **Script import validator** (`scanners/script_validator.py`)
  - [ ] Verify `scripts/*.py` can resolve their imports via AST (no actual import execution)
- [ ] **Test-FR coverage mapper** (`scanners/test_coverage.py`)
  - [ ] Map TC-xxx references in Features to actual test files
  - [ ] Flag TCs with no test function, test files with no FR reference
- [ ] **Config drift detector** (`scanners/config_drift.py`)
  - [ ] Auth decorators in code but not in project YAML config
- [ ] **Migration health check** (`scanners/migration_health.py`)
  - [ ] Multiple Alembic heads, database not at HEAD, migrations without downgrade
- [ ] Register all scanners in `scanners/__init__.py`
- [ ] Tests for each scanner

### Acceptance Criteria

1. All 10 scanners operational (4 existing + 6 new)
2. Impact analyzer correctly traces reverse dependencies
3. `cli.py scan --project vms --scanner all` runs all 10 scanners
4. All tests pass

### Dependencies

- Phase 4a (finding→WorkItem pipeline available for all scanners)

---

## Phase 6: PM & Polish

> **Goal:** Project management features for longer-term planning, plus dashboard polish.
>
> **Spec reference:** [Extended Features § Project Management](extended_features.md#4-project-management-features)

### Deliverables

- [ ] **Sprint planning view**
  - [ ] Backlog triage (drag between priority levels)
  - [ ] "This sprint" selection (1–2 week window)
  - [ ] Effort totals (S=1, M=2, L=4, XL=8 points)
  - [ ] Auto-suggest top 5 items based on priority, age, dependency readiness
- [ ] **Milestone tracking**
  - [ ] Group WorkItems and Features under milestones
  - [ ] Completion percentage per milestone
  - [ ] Velocity-based estimated completion date
- [ ] **Velocity tracking**
  - [ ] Items completed per session (from session logs)
  - [ ] Average session duration
  - [ ] Completion rate by category (bugs vs features vs debt)
- [ ] **Quarterly review generator**
  - [ ] Auto-summarize shipped features, debt resolved, health trend
  - [ ] Feature adoption rates (from 90-day reviews)
- [ ] **Data health sub-score** (for projects with data pipelines)
  - [ ] Import freshness, sync errors, schema drift
  - [ ] Secondary score on dashboard: `Data Health: 85/100`
- [ ] **Cross-project health summary**
  - [ ] Dashboard landing shows health for all configured projects
- [ ] **Feature Pulse**
  - [ ] Git activity → dormant feature detection
- [ ] Dashboard UX polish pass
- [ ] Tests for Phase 6

### Acceptance Criteria

1. Sprint planning view supports backlog triage and effort estimation
2. Milestone tracking shows completion % and projected dates
3. Quarterly review generates a useful summary document
4. Cross-project view works with 2+ configured projects
5. All tests pass

### Dependencies

- Phase 4c (trends and time-scoped views), Phase 4b (session logs for velocity)

