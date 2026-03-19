"""CLI entry point for Polaris DevTools.

Usage:
    python cli.py scan --project vms --scanner coupling
    python cli.py briefing --project vms
    python cli.py receipt --project vms
    python cli.py export tech-debt --project vms
    python cli.py import tech-debt --project vms
    python cli.py routes --project vms
    python cli.py context --project vms
"""

import json

import click
from rich.console import Console
from rich.table import Table

from config_loader import load_all_project_configs

console = Console()


def get_project_config(project_key):
    """Load and validate a project config by key."""
    configs = load_all_project_configs()
    if project_key not in configs:
        available = ", ".join(configs.keys()) if configs else "(none)"
        raise click.ClickException(
            f"Project '{project_key}' not found. Available: {available}"
        )
    config = configs[project_key]
    warnings = config.validate()
    for w in warnings:
        click.echo(click.style(f"  ⚠ {w}", fg="yellow"), err=True)
    return config


def get_app():
    """Lazy import of Flask app to avoid circular imports."""
    from app import create_app

    return create_app()


@click.group()
@click.version_option(version="0.1.0", prog_name="polaris-devtools")
def cli():
    """Polaris DevTools — Development management companion."""
    pass


# ─── Daily Commands (flat, top-level) ─────────────────────


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option("--scanner", "-s", default="all", help="Scanner to run (or 'all')")
def scan(project, scanner):
    """Run codebase scanners."""
    config = get_project_config(project)

    # Import scanner registry
    from scanners import SCANNER_REGISTRY
    from scanners.base import SCANNER_REGISTRY as BASE_REGISTRY

    registry = {**BASE_REGISTRY, **SCANNER_REGISTRY}

    if scanner == "all":
        scanners_to_run = list(registry.keys())
    elif scanner in registry:
        scanners_to_run = [scanner]
    else:
        available = ", ".join(registry.keys())
        raise click.ClickException(
            f"Scanner '{scanner}' not found. Available: {available}"
        )

    console.print(f"\n  [bold]Scanning {config.project_name}[/bold]\n")

    app = get_app()
    with app.app_context():
        from models import db, ScanResult

        for scanner_name in scanners_to_run:
            scanner_cls = registry[scanner_name]
            scanner_instance = scanner_cls()

            console.print(f"  ⏳ Running {scanner_name}...", end="")

            result = scanner_instance.scan(config)

            # Determine severity
            if result.critical_count > 0:
                badge = "[red]CRITICAL[/red]"
            elif result.warning_count > 0:
                badge = "[yellow]WARNING[/yellow]"
            else:
                badge = "[green]CLEAN[/green]"

            console.print(
                f"\r  {badge}  {scanner_name}: "
                f"{result.critical_count} critical, "
                f"{result.warning_count} warnings, "
                f"{result.info_count} info  "
                f"({result.scanned_files} files, {result.duration_ms}ms)"
            )

            # Store results
            result_data = {
                "findings": [
                    {
                        "file": f.file,
                        "line": f.line,
                        "message": f.message,
                        "severity": f.severity,
                        "details": f.details,
                    }
                    for f in result.findings
                ],
                "scanned_files": result.scanned_files,
                "errors": result.errors,
                "duration_ms": result.duration_ms,
            }

            # Include route registry if present
            if hasattr(result, "route_registry"):
                result_data["route_registry"] = result.route_registry

            severity = (
                "critical"
                if result.critical_count > 0
                else ("warning" if result.warning_count > 0 else "info")
            )

            scan_record = ScanResult(
                project=project,
                scanner=scanner_name,
                scanner_version=scanner_instance.version,
                severity=severity,
                finding_count=len(result.findings),
                result_json=json.dumps(result_data),
            )
            db.session.add(scan_record)

            # Print findings
            if result.findings:
                console.print()
                for f in result.findings:
                    icon = (
                        "🔴"
                        if f.severity == "critical"
                        else "🟡" if f.severity == "warning" else "🔵"
                    )
                    loc = f"{f.file}:{f.line}" if f.line else f.file
                    console.print(f"    {icon} {loc}")
                    console.print(f"       {f.message}")
                console.print()

            if result.errors:
                for err in result.errors:
                    console.print(f"    [dim red]⚠ {err}[/dim red]")

        db.session.commit()

    console.print("  [green]✓ Scan complete[/green]\n")


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def briefing(project):
    """Generate pre-session briefing."""
    config = get_project_config(project)
    click.echo(f"\n  Generating briefing for {config.project_name}...")
    click.echo("  (Session tooling not yet implemented — Phase 4)\n")


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def receipt(project):
    """Generate post-session receipt."""
    config = get_project_config(project)
    click.echo(f"\n  Generating receipt for {config.project_name}...")
    click.echo("  (Session tooling not yet implemented — Phase 4)\n")


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option(
    "--filter", "-f", "route_filter", default=None, help="Filter routes by URL pattern"
)
def routes(project, route_filter):
    """List all routes in the project from latest scan."""
    app = get_app()
    with app.app_context():
        from models import ScanResult

        # Get latest coupling scan
        latest = (
            ScanResult.query.filter_by(project=project, scanner="coupling")
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )

        if not latest or not latest.result_json:
            console.print(
                "\n  [yellow]No coupling scan found. "
                "Run: cli.py scan -p {project} -s coupling[/yellow]\n"
            )
            return

        data = json.loads(latest.result_json)
        registry = data.get("route_registry", [])

        if not registry:
            console.print("\n  [yellow]No routes found in scan results.[/yellow]\n")
            return

        # Apply filter
        if route_filter:
            registry = [
                r
                for r in registry
                if route_filter.lower() in r.get("url_pattern", "").lower()
            ]

        # Build Rich table
        table = Table(title=f"Route Registry — {project.upper()}", show_lines=False)
        table.add_column("Method", style="bold cyan", width=8)
        table.add_column("URL Pattern", style="white")
        table.add_column("Function", style="green")
        table.add_column("Auth", style="yellow")
        table.add_column("Template", style="dim")
        table.add_column("File:Line", style="dim")

        for r in sorted(registry, key=lambda x: x.get("url_pattern", "")):
            methods = ",".join(r.get("methods", ["GET"]))
            auth = ", ".join(r.get("auth_decorators", [])) or "—"
            templates = ", ".join(r.get("templates", [])) or "—"
            loc = f"{r.get('file', '')}:{r.get('line', '')}"

            table.add_row(
                methods,
                r.get("url_pattern", ""),
                r.get("function_name", ""),
                auth,
                templates,
                loc,
            )

        console.print()
        console.print(table)
        console.print(f"\n  {len(registry)} routes total\n")


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option(
    "--scanner",
    "-s",
    default="all",
    help="Scanner to generate context for (or 'all')",
)
@click.option("--output", "-o", default=None, help="Output file path")
@click.option("--copy", "copy_clipboard", is_flag=True, help="Copy to clipboard")
def context(project, scanner, output, copy_clipboard):
    """Generate AI context packets from scan findings."""
    config = get_project_config(project)
    console.print(f"\n  [bold]AI Context Packet — {config.project_name}[/bold]\n")

    app = get_app()
    with app.app_context():
        from models import ScanResult
        from utils.context_formatter import format_all_findings

        project_root = getattr(config, "project_root", None)

        scanners_to_process = (
            ["coupling", "security"] if scanner == "all" else [scanner]
        )

        all_output = []

        for scanner_name in scanners_to_process:
            latest = (
                ScanResult.query.filter_by(project=project, scanner=scanner_name)
                .order_by(ScanResult.scanned_at.desc())
                .first()
            )

            if not latest or not latest.result_json:
                console.print(f"  [yellow]No {scanner_name} scan results.[/yellow]")
                continue

            data = json.loads(latest.result_json)
            findings = data.get("findings", [])
            errors = data.get("errors", [])

            if not findings:
                console.print(f"  [green]✓ {scanner_name}: no findings[/green]")
                continue

            formatted = format_all_findings(
                findings, scanner_name, project_root, errors
            )
            all_output.append(formatted)
            console.print(f"  📋 {scanner_name}: {len(findings)} findings formatted")

        if not all_output:
            console.print("\n  [yellow]No findings to format.[/yellow]\n")
            return

        full_text = "\n\n".join(all_output)

        if output:
            from pathlib import Path

            Path(output).write_text(full_text, encoding="utf-8")
            console.print(f"\n  📄 Written to: {output}")
        elif copy_clipboard:
            try:
                import subprocess

                process = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
                process.communicate(full_text.encode("utf-8"))
                console.print("\n  📋 Copied to clipboard!")
            except Exception:
                console.print(
                    "\n  [yellow]Clipboard not available. "
                    "Use --output to write to file.[/yellow]"
                )
        else:
            console.print("\n" + full_text)

    console.print("\n  [green]✓ Context packet generated[/green]\n")


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option("--title", required=True, help="Bug title")
@click.option(
    "--priority", default="medium", help="Priority (critical/high/medium/low)"
)
def bug(project, title, priority):
    """Quick-capture a bug report."""
    app = get_app()
    with app.app_context():
        from models import db, WorkItem

        item = WorkItem(
            project=project,
            title=title,
            category="bug",
            priority=priority,
            status="backlog",
        )
        db.session.add(item)
        db.session.commit()

        console.print(f"\n  🐛 Bug created: #{item.id} — {title} [{priority}]")
        console.print(
            f"  [dim]View at http://localhost:5001/work-items/{item.id}[/dim]\n"
        )


@cli.command(name="feature-request")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option("--title", required=True, help="Feature request title")
def feature_request(project, title):
    """Quick-capture a feature request."""
    app = get_app()
    with app.app_context():
        from models import db, WorkItem

        item = WorkItem(
            project=project,
            title=title,
            category="feature",
            priority="medium",
            status="backlog",
        )
        db.session.add(item)
        db.session.commit()

        console.print(f"\n  💡 Feature request created: #{item.id} — {title}")
        console.print(
            f"  [dim]View at http://localhost:5001/work-items/{item.id}[/dim]\n"
        )


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option("--last", "-n", default=5, help="Number of sessions to show")
def sessions(project, last):
    """View session history."""
    click.echo(f"\n  Session history (last {last})...")
    click.echo("  (Session history not yet implemented — Phase 4)\n")


# ─── Grouped Commands (import/export) ─────────────────────


@cli.group(name="import")
def import_group():
    """Import data from project docs into DevTools."""
    pass


@import_group.command(name="tech-debt")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def import_tech_debt(project):
    """Import tech debt items from tech_debt.md."""
    config = get_project_config(project)
    console.print(f"\n  [bold]Importing tech debt for {config.project_name}[/bold]\n")

    # Resolve tech_debt.md path
    from pathlib import Path

    tech_debt_path = None
    if hasattr(config, "managed_docs"):
        for doc in config.managed_docs:
            if hasattr(doc, "name") and doc.name == "tech_debt":
                tech_debt_path = Path(config.project_root) / doc.source_path
                break

    if not tech_debt_path or not tech_debt_path.exists():
        # Fallback to common location
        root = Path(config.project_root)
        candidates = [
            root / "documentation" / "content" / "developer" / "tech_debt.md",
            root / "docs" / "tech_debt.md",
            root / "tech_debt.md",
        ]
        for c in candidates:
            if c.exists():
                tech_debt_path = c
                break

    if not tech_debt_path or not tech_debt_path.exists():
        raise click.ClickException(
            f"Could not find tech_debt.md for project '{project}'. "
            f"Checked common locations."
        )

    console.print(f"  📄 Source: {tech_debt_path}")

    app = get_app()
    with app.app_context():
        from importers.tech_debt_importer import TechDebtImporter

        importer = TechDebtImporter()
        stats = importer.import_from_file(tech_debt_path, project=project)

        console.print(f"  ✅ Created: {stats['created']} items")
        if stats["errors"]:
            for err in stats["errors"]:
                console.print(f"  [red]⚠ {err}[/red]")

    console.print("\n  [green]✓ Import complete[/green]\n")


@import_group.command(name="status-tracker")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def import_status_tracker(project):
    """Import features from development_status_tracker.md."""
    config = get_project_config(project)
    console.print(
        f"\n  [bold]Importing status tracker for {config.project_name}[/bold]\n"
    )

    from pathlib import Path

    # Resolve status tracker path
    tracker_path = None
    if hasattr(config, "managed_docs"):
        for doc in config.managed_docs:
            if hasattr(doc, "name") and doc.name == "status_tracker":
                tracker_path = Path(config.project_root) / doc.source_path
                break

    if not tracker_path or not tracker_path.exists():
        root = Path(config.project_root)
        candidates = [
            root
            / "documentation"
            / "content"
            / "developer"
            / "development_status_tracker.md",
            root / "docs" / "development_status_tracker.md",
            root / "development_status_tracker.md",
        ]
        for c in candidates:
            if c.exists():
                tracker_path = c
                break

    if not tracker_path or not tracker_path.exists():
        raise click.ClickException(
            f"Could not find development_status_tracker.md for project '{project}'."
        )

    console.print(f"  📄 Source: {tracker_path}")

    app = get_app()
    with app.app_context():
        from importers.status_tracker_importer import StatusTrackerImporter

        importer = StatusTrackerImporter()
        stats = importer.import_from_file(tracker_path, project=project)

        console.print(f"  ✅ Created: {stats['created']} features")
        console.print(f"  🔄 Updated: {stats['updated']} features")
        if stats["errors"]:
            for err in stats["errors"]:
                console.print(f"  [red]⚠ {err}[/red]")

    console.print("\n  [green]✓ Import complete[/green]\n")


@cli.group(name="export")
def export_group():
    """Export DevTools data to project docs."""
    pass


@export_group.command(name="tech-debt")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option(
    "--output", "-o", default=None, help="Output file path (default: auto-detect)"
)
def export_tech_debt(project, output):
    """Export tech debt items to tech_debt.md."""
    config = get_project_config(project)
    console.print(f"\n  [bold]Exporting tech debt for {config.project_name}[/bold]\n")

    from pathlib import Path

    # Resolve output path
    if output:
        output_path = Path(output)
    else:
        # Try to determine from config
        output_path = None
        if hasattr(config, "managed_docs"):
            for doc in config.managed_docs:
                if hasattr(doc, "name") and doc.name == "tech_debt":
                    output_path = Path(config.project_root) / doc.source_path
                    break

        if not output_path:
            output_path = Path(config.project_root) / "tech_debt_export.md"

    app = get_app()
    with app.app_context():
        from exporters.tech_debt_exporter import TechDebtExporter

        exporter = TechDebtExporter()
        stats = exporter.export(project, output_path)

        console.print(f"  📄 Output: {stats['file']}")
        console.print(f"  📊 Active: {stats['active']}, Resolved: {stats['resolved']}")

        # Try git staging
        if hasattr(config, "project_root"):
            staged = exporter.git_stage(output_path, Path(config.project_root))
            if staged:
                console.print("  📦 Auto-staged in git")

    console.print("\n  [green]✓ Export complete[/green]\n")


@export_group.command(name="status-tracker")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option(
    "--output", "-o", default=None, help="Output file path (default: auto-detect)"
)
def export_status_tracker(project, output):
    """Export features to development_status_tracker.md."""
    config = get_project_config(project)
    console.print(
        f"\n  [bold]Exporting status tracker for {config.project_name}[/bold]\n"
    )

    from pathlib import Path

    # Resolve output path
    if output:
        output_path = Path(output)
    else:
        # Try to determine from managed_docs config
        managed = config.managed_docs.get("status_tracker")
        if managed:
            output_path = Path(config.project_root) / managed.path
        else:
            output_path = Path(config.project_root) / "status_tracker_export.md"

    app = get_app()
    with app.app_context():
        from exporters.status_tracker_exporter import StatusTrackerExporter

        exporter = StatusTrackerExporter()
        stats = exporter.export(project, output_path)

        console.print(f"  📄 Output: {stats['file']}")
        console.print(
            f"  📊 Total: {stats['total']} features "
            f"(✅ {stats['implemented']}, 🔧 {stats['partial']}, 📋 {stats['pending']})"
        )

        # Try git staging
        staged = exporter.git_stage(output_path, Path(config.project_root))
        if staged:
            console.print("  📦 Auto-staged in git")

    console.print("\n  [green]✓ Export complete[/green]\n")


@export_group.command(name="sync")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def export_sync(project):
    """Sync all dirty managed docs (export-on-receipt hook)."""
    config = get_project_config(project)
    console.print(f"\n  [bold]Syncing dirty exports for {config.project_name}[/bold]\n")

    from pathlib import Path
    from exporters.tech_debt_exporter import TechDebtExporter
    from exporters.status_tracker_exporter import StatusTrackerExporter

    exporters_map = {
        "tech_debt": (TechDebtExporter, "WorkItem"),
        "status_tracker": (StatusTrackerExporter, "Feature"),
    }

    app = get_app()
    with app.app_context():
        from models import WorkItem, Feature

        synced = 0
        for doc_key, managed in config.managed_docs.items():
            exporter_cls_pair = exporters_map.get(doc_key)
            if not exporter_cls_pair:
                continue

            exporter_cls, model_name = exporter_cls_pair
            exporter = exporter_cls()

            # Check if records have been updated since last export
            if model_name == "WorkItem":
                latest = WorkItem.query.order_by(WorkItem.updated_at.desc()).first()
                latest_update = latest.updated_at if latest else None
            elif model_name == "Feature":
                latest = Feature.query.order_by(Feature.updated_at.desc()).first()
                latest_update = latest.updated_at if latest else None
            else:
                continue

            if latest_update and exporter.is_dirty(project, doc_key, latest_update):
                output_path = Path(config.project_root) / managed.path
                exporter.export(project, output_path)
                exporter.git_stage(output_path, Path(config.project_root))
                console.print(f"  ✅ Exported: {doc_key} → {managed.path}")
                synced += 1
            else:
                console.print(f"  ⏭  Clean: {doc_key} (no changes)")

        if synced:
            console.print(f"\n  [green]✓ Synced {synced} export(s)[/green]\n")
        else:
            console.print("\n  [dim]No dirty exports to sync[/dim]\n")


@export_group.command(name="all")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def export_all(project):
    """Export all managed docs."""
    config = get_project_config(project)
    click.echo(f"\n  Exporting all managed docs for {config.project_name}...")
    click.echo("  (Full export not yet implemented — Phase 3)\n")


# ─── Utility Commands ─────────────────────────────────────


@cli.command()
@click.option("--project", "-p", default=None, help="Project key (or all if omitted)")
def stats(project):
    """Show project statistics."""
    from models import WorkItem, Feature, ScanResult, SessionLog

    app = get_app()
    with app.app_context():
        work_count = WorkItem.query.count()
        feature_count = Feature.query.count()
        scan_count = ScanResult.query.count()
        session_count = SessionLog.query.count()

    click.echo("\n  DevTools Statistics")
    click.echo("  ──────────────────")
    click.echo(f"  Work Items:   {work_count}")
    click.echo(f"  Features:     {feature_count}")
    click.echo(f"  Scan Results: {scan_count}")
    click.echo(f"  Sessions:     {session_count}\n")


if __name__ == "__main__":
    cli()
