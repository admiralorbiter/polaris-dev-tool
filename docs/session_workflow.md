# Session Workflow

> Pre-session briefings, the 9-layer change receipt, and post-session automation.

**Last Updated:** March 2026

---

## Overview

Every dev session has two bookends:

1. **Briefing** (before) — "What should I know before I start?"
2. **Receipt** (after) — "What did I change and what needs follow-up?"

Both are available via CLI and dashboard.

---

## Briefing

### Command

```bash
python cli.py briefing --project vms
```

### What It Generates

The briefing is a structured snapshot of project state. It answers: "What do I need to know right now?"

#### 1. Git State

| Check | Source |
|:------|:-------|
| Current branch | `repo.active_branch` |
| Uncommitted changes | `repo.is_dirty()` + `repo.untracked_files` |
| Ahead/behind origin | `repo.iter_commits('origin/main..HEAD')` |
| Stale branches (14+ days) | Branch last-commit dates |

#### 2. Critical Scan Findings

Latest `ScanResult` records with `severity="critical"`:
- Unprotected routes (security scanner)
- Broken template references (coupling scanner)
- Scripts with unresolved imports (script validator)

#### 3. In-Progress Work Items

`WorkItem.query.filter_by(status="in_progress", project=project)` — what you said you were working on last time.

#### 4. Upcoming Reviews

`Feature.query.filter(Feature.next_review <= today + 14_days)` — features approaching or past their 90-day review.

#### 5. Doc Freshness Alerts

For each entry in `watched_docs`:
- Count git commits to watched code paths since the doc's last `git log` date
- Weight by `freshness_weights` priority
- Flag if code changed 3+ times without a doc update

#### 6. Managed Doc Status

For each entry in `managed_docs`:
- Time since last export
- Count of records changed since last export (dirty count)

### Briefing Storage

The briefing is stored as JSON in `SessionLog.briefing_json` and displayed as a formatted table in the terminal (via `rich`).

---

## Receipt — The 9-Layer Matrix

### Command

```bash
python cli.py receipt --project vms
```

### How It Works

1. Reads `commit_range_start` from the session's briefing
2. Gets current `HEAD` as `commit_range_end`
3. Runs `git diff --stat` between the two
4. Classifies every changed file into one of 9 layers
5. Runs layer-specific analysis
6. Generates alerts for missing coverage

### The 9 Layers

| # | Layer | Detection Method | Alert Condition |
|:--|:------|:----------------|:----------------|
| 1 | **Files Changed** | `git diff --stat` | None (informational) |
| 2 | **Routes Added/Modified** | AST parse for `@app.route` / `@bp.route` decorators in changed `.py` files | New route has no auth decorator |
| 3 | **Models Touched** | Changed files in `models/` or files containing `db.Column` | Model change without migration |
| 4 | **Templates Changed** | Changed `.html` files in `templates/` | Template changed but no route references it |
| 5 | **Tests Added/Modified** | Changed files in `tests/` | Code changed but no tests changed |
| 6 | **Services Affected** | Changed files in `services/` | Service changed but no tests updated |
| 7 | **Docs Updated** | Changed files in `documentation/` | ⚠ Code changed but managed docs not exported |
| 8 | **Dependencies Changed** | `requirements.txt`, `package.json` diffs | Dependency added/removed |
| 9 | **Config Changes** | `.env`, `config.py`, YAML file diffs | Config changed |

### Layer 7 Drift Detection

This is the most valuable alert. The receipt checks:

1. Were any `models/` or `routes/` files changed? → If yes, check if `tech_debt.md` or `status_tracker.md` have pending exports
2. Were any new routes added? → Flag if `api_reference.md` (watched doc) wasn't updated
3. Were any test files changed? → Flag if `smoke_tests.md` (watched doc) is stale

### Alerts

Alerts fall into three categories:

| Type | Action |
|:-----|:-------|
| **Auto-resolved** | Export dirty docs, auto-stage them |
| **WorkItem created** | "API docs need update" → new WorkItem with `category=review` |
| **Warning displayed** | "No tests changed despite route additions" |

---

## Post-Receipt Automation

After the receipt is generated, these hooks fire automatically:

### 1. Auto-Export Dirty Docs

```python
for doc_config in project["managed_docs"].values():
    if exporter.is_dirty(doc_config):
        exporter.export(doc_config)
        # Writes rendered markdown to project repo
```

### 2. Auto-Stage Exported Files

```python
repo = git.Repo(project_root)
for exported_path in exported_files:
    repo.index.add([exported_path])
```

### 3. Create Drift WorkItems

For each Layer 7 alert:
```python
WorkItem.create(
    project=project_key,
    source_id=f"DRIFT-{date.today().isoformat()}",
    title=f"Update {doc_name} — code changed since last edit",
    category="review",
    priority="medium",
    status="backlog",
    notes=f"Auto-created by session receipt. {change_count} code changes since last doc update."
)
```

### 4. Persist Session Log

```python
session_log.receipt_json = json.dumps(receipt)
session_log.ended_at = datetime.utcnow()
session_log.commit_range_end = repo.head.commit.hexsha
session_log.files_changed = json.dumps(changed_files)
session_log.docs_exported = json.dumps(exported_paths)
db.session.commit()
```

---

## Diff-Aware vs Full Scanning

| Context | Scan Scope | Reason |
|:--------|:-----------|:-------|
| `cli.py briefing` | Diff-aware (since last session) | Speed — only recent changes matter |
| `cli.py receipt` | Diff-aware (session commit range) | Relevance — only this session's changes |
| `cli.py scan` | Full project | Comprehensive — catch everything |
| Dashboard refresh | Cached results | Performance — no re-scan |

Diff-aware scanning uses:
```python
changed_files = [
    item.a_path for item in
    repo.commit(start_sha).diff(repo.commit(end_sha))
]
```

---

## CLI Command Reference

```bash
# Start a session (records git HEAD, generates briefing)
python cli.py briefing --project vms

# End a session (generates receipt, exports docs, stages files)
python cli.py receipt --project vms

# Manual export (outside session context)
python cli.py export --project vms --target all
python cli.py export --project vms --target tech_debt

# View session history
python cli.py sessions --project vms --last 5
```
