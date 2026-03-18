# Polaris DevTools Companion

> A standalone development management system that runs alongside your projects.

**Owns** tech debt, features, and status tracking as structured data — **exports** rendered markdown back to project repos — **scans** codebases for issues — **briefs** you before each session and **receipts** what changed after.

---

## Quick Links

| Doc | What It Covers |
|:----|:--------------|
| [Architecture](docs/architecture.md) | Source-of-truth model, ownership boundaries, export engine, scanner protocol |
| [Data Models](docs/data_models.md) | WorkItem, Feature, ScanResult, SessionLog — full field specs |
| [Config Schema](docs/config_schema.md) | Project YAML configuration with annotated examples |
| [Session Workflow](docs/session_workflow.md) | Pre-session briefing, 9-layer receipt matrix, post-receipt automation |
| [Scanner Specs](docs/scanner_specs.md) | All 10 scanners — checks, severity, algorithms |
| [Extended Features](docs/extended_features.md) | Health score, route registry, AI context generator, PM tools |
| [Roadmap](docs/roadmap.md) | Build phases 0–5 with acceptance criteria |
| [Development Process](docs/development_process.md) | Coding standards, testing, git workflow, how to add scanners |

---

## Key Principles

1. **Source of truth** — Structured data lives in the DB; markdown is a rendered export
2. **Zero coupling** — Scans the filesystem, never imports from target projects
3. **CLI first, UI second** — Every feature works from the terminal
4. **Fail open** — Scanners skip broken files, never crash a full scan

---

## Tech Stack

Flask · SQLite (WAL) · SQLAlchemy · Click · Rich · GitPython · Vanilla JS/CSS

---

## Status

**Phase 0: Documentation** — Complete ✅

Next: [Phase 1: Foundation + Export Engine](docs/roadmap.md#phase-1-foundation--export-engine)
