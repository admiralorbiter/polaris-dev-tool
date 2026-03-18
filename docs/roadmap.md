# Roadmap

> Build phases with acceptance criteria and dependencies.
>
> See also: [Extended Features](extended_features.md) for detailed specs on health score, route registry, AI context, and PM features.

**Last Updated:** March 2026

---

## Phase Overview

| Phase | Name | Key Deliverable | Est. Sessions |
|:------|:-----|:----------------|:-------------|
| 0 | Documentation | Project docs (this phase) | 1 |
| 1 | Foundation + Export Engine | Running app with DB, export, basic dashboard | 2–3 |
| 2 | Scanners + Import | Coupling/security scanners, tech debt import | 3–4 |
| 3 | Work Board + Features | CRUD, lifecycle tracking, freshness scanner | 2–3 |
| 4 | Session Tooling | Briefings, receipts, 9-layer matrix | 2–3 |
| 5 | Polish + Extended Scanners | Trend tracking, additional scanners | 2–3 |

---

## Phase 0: Documentation ✅

> [!NOTE]
> You are here.

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

## Phase 1: Foundation + Export Engine

### Deliverables

- [ ] Flask app scaffold (`app.py`, `config.py`)
- [ ] All 4 database models (`models.py`)
- [ ] SQLite with WAL mode enabled
- [ ] Alembic migration setup + initial migration
- [ ] VMS project config YAML (`projects/vms.yaml`)
- [ ] Config loader with validation
- [ ] Base template with dark theme + navigation shell
- [ ] Dashboard page (placeholder panels)
- [ ] Health-check endpoint (`GET /api/health`)
- [ ] Export engine base:
  - [ ] Markdown renderer interface
  - [ ] Dirty-flag tracking (`last_export_at` per managed doc)
  - [ ] Git auto-stage on export
- [ ] CLI scaffolding (Click groups: `scan`, `briefing`, `receipt`, `export`, `import`)
- [ ] `.env` support via `python-dotenv`
- [ ] `.gitignore`
- [ ] `requirements.txt`
- [ ] Basic test setup (`conftest.py`, model tests)

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

## Phase 3: Work Board + Feature Lifecycle

### Deliverables

- [ ] WorkItem CRUD routes and API
  - [ ] Create, read, update, delete
  - [ ] Filter by status, priority, category, tags
  - [ ] Dependency graph visualization
- [ ] Feature CRUD routes and API
  - [ ] Create, read, update
  - [ ] Auto-set `next_review` on ship date
  - [ ] Filter by domain, status, implementation status
- [ ] Work board template (table view + optional kanban)
  - [ ] Archive toggle (show/hide resolved items)
  - [ ] Priority sorting
- [ ] Feature lifecycle template
  - [ ] Status badges with color coding
  - [ ] 90-day review countdown
- [ ] Status tracker importer (`importers/status_tracker_importer.py`)
  - [ ] Parse VMS `development_status_tracker.md` (203 FRs)
  - [ ] Create Feature records with domain, test cases, status
- [ ] Status tracker exporter (`exporters/status_tracker_exporter.py`)
- [ ] Doc freshness scanner (`scanners/doc_freshness.py`)
  - [ ] Uses `watched_docs` config with priority weighting
- [ ] Export-on-receipt integration
  - [ ] Auto-export dirty managed docs at session end
  - [ ] Auto-stage exported files
- [ ] **Project health score** (enhanced — 5-component weighted system)
  - [x] ~~Basic scan-based score (0–100, color-coded gauge on dashboard)~~ _(shipped in Phase 2)_
  - [ ] Score engine: add doc freshness + debt load + test activity + work flow components
  - [ ] CLI: single line in briefing output
- [ ] **Bug/feature quick-capture** (CLI shortcuts for WorkItem creation)
  - [ ] `cli.py bug --project vms --title "..." --priority high`
  - [ ] `cli.py feature-request --project vms --title "..."`
- [ ] CRUD tests
- [ ] Importer/exporter tests

### Acceptance Criteria

1. Work board displays all imported tech debt items
2. Features display all imported FRs with correct status symbols
3. Archiving a WorkItem removes it from the active board
4. Doc freshness scanner correctly flags stale `smoke_tests.md`
5. Export-on-receipt writes and stages updated markdown files
6. All tests pass

### Dependencies

- Phase 2 (import/export infrastructure, scanner framework)

---

## Phase 4: Session Tooling

### Deliverables

- [ ] Pre-session briefing generator
  - [ ] 6-point checklist (git, scans, work items, reviews, freshness, export status)
  - [ ] Rich terminal output
- [ ] Post-session receipt generator
  - [ ] 9-layer change matrix
  - [ ] Commit range tracking
  - [ ] Layer 7 drift detection
- [ ] Receipt post-hooks
  - [ ] Auto-export dirty docs
  - [ ] Auto-stage exported files
  - [ ] Auto-create drift WorkItems
- [ ] Impact analyzer scanner (`scanners/impact_analyzer.py`)
  - [ ] Reverse dependency graph builder
  - [ ] "What breaks if I change X" query
- [ ] **Commit message generator** (auto-draft from 9-layer receipt)
  - [ ] Structured message with summary line + body
  - [ ] Copy to clipboard option
- [ ] **AI context generator** (enhanced — task templates and live DB sections)
  - [x] ~~Scan-based context packets with code snippets~~ _(shipped in Phase 2)_
  - [x] ~~CLI: `cli.py context -p vms -s security [--output | --copy]`~~ _(shipped in Phase 2)_
  - [x] ~~UI copy buttons on scan detail page~~ _(shipped in Phase 2)_
  - [ ] Static sections from config + AI collab guide
  - [ ] Live sections from DB (active items, recent sessions, findings)
  - [ ] Task-specific templates (sprint-planning, retro, code-review, debugging)
- [ ] Session log persistence
- [ ] Dashboard: session history view
- [ ] CLI: `python cli.py briefing --project vms`
- [ ] CLI: `python cli.py receipt --project vms`
- [ ] Session tooling tests

### Acceptance Criteria

1. Briefing correctly reports git state, critical findings, and in-progress items
2. Receipt correctly classifies changes into 9 layers
3. Layer 7 drift detection flags undocumented changes
4. Post-receipt hooks export and stage files
5. Session history is queryable
6. All tests pass

### Dependencies

- Phase 3 (work board, features, freshness scanner)

---

## Phase 5: Polish + Extended Scanners

### Deliverables

- [ ] Obsolescence scanner
- [ ] Script import validator
- [ ] Test-FR coverage mapper
- [ ] Config drift detector  
- [ ] Migration health check
- [ ] Historical trend tracking (finding counts over time)
- [ ] Health score trend sparkline (last 10 sessions)
- [ ] Cross-project health summary on dashboard landing page
- [ ] Feature Pulse (git activity → dormant features)
- [ ] **Sprint planning view** (backlog triage, effort totals, dependency graph)
- [ ] **Milestone tracking** (group items, completion %, velocity-based ETA)
- [ ] **Velocity tracking** (items/session, completion rate by category)
- [ ] **Quarterly review generator** (auto-summarize shipped features, debt resolved, health trend)
- [ ] **Data health sub-score** (import freshness, sync errors, schema drift)
- [ ] Dashboard polish and UX refinement

### Acceptance Criteria

1. All 10 scanners operational
2. Dashboard shows trend charts for scan findings
3. Cross-project summary displays health for all configured projects
4. All tests pass

### Dependencies

- Phase 4 (session tooling, all core infrastructure)
