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

import click

from config_loader import load_all_project_configs


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
    click.echo(f"\n  Scanning {config.project_name} with '{scanner}' scanner...")
    click.echo("  (Scanners not yet implemented — Phase 2)\n")


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
@click.option("--filter", "-f", "route_filter", default=None, help="Filter routes by URL pattern")
def routes(project, route_filter):
    """List all routes in the project."""
    config = get_project_config(project)
    click.echo(f"\n  Route registry for {config.project_name}...")
    click.echo("  (Route registry not yet implemented — Phase 2)\n")


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option("--template", "-t", default=None, help="Task template (sprint-planning, retro, code-review)")
@click.option("--copy", "copy_clipboard", is_flag=True, help="Copy to clipboard")
def context(project, template, copy_clipboard):
    """Generate AI context document."""
    config = get_project_config(project)
    click.echo(f"\n  Generating AI context for {config.project_name}...")
    click.echo("  (AI context not yet implemented — Phase 4)\n")


@cli.command()
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option("--title", required=True, help="Bug title")
@click.option("--priority", default="medium", help="Priority (critical/high/medium/low)")
def bug(project, title, priority):
    """Quick-capture a bug report."""
    click.echo(f"\n  Creating bug: {title} [{priority}]")
    click.echo("  (Bug capture not yet implemented — Phase 3)\n")


@cli.command(name="feature-request")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
@click.option("--title", required=True, help="Feature request title")
def feature_request(project, title):
    """Quick-capture a feature request."""
    click.echo(f"\n  Creating feature request: {title}")
    click.echo("  (Feature capture not yet implemented — Phase 3)\n")


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
    click.echo(f"\n  Importing tech debt from {config.project_name}...")
    click.echo("  (Tech debt importer not yet implemented — Phase 2)\n")


@import_group.command(name="status-tracker")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def import_status_tracker(project):
    """Import features from development_status_tracker.md."""
    config = get_project_config(project)
    click.echo(f"\n  Importing status tracker from {config.project_name}...")
    click.echo("  (Status tracker importer not yet implemented — Phase 3)\n")


@cli.group(name="export")
def export_group():
    """Export DevTools data to project docs."""
    pass


@export_group.command(name="tech-debt")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def export_tech_debt(project):
    """Export tech debt items to tech_debt.md."""
    config = get_project_config(project)
    click.echo(f"\n  Exporting tech debt for {config.project_name}...")
    click.echo("  (Tech debt exporter not yet implemented — Phase 2)\n")


@export_group.command(name="status-tracker")
@click.option("--project", "-p", required=True, help="Project key (e.g., 'vms')")
def export_status_tracker(project):
    """Export features to development_status_tracker.md."""
    config = get_project_config(project)
    click.echo(f"\n  Exporting status tracker for {config.project_name}...")
    click.echo("  (Status tracker exporter not yet implemented — Phase 3)\n")


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
    from app import create_app
    from models import WorkItem, Feature, ScanResult, SessionLog

    app = create_app()
    with app.app_context():
        work_count = WorkItem.query.count()
        feature_count = Feature.query.count()
        scan_count = ScanResult.query.count()
        session_count = SessionLog.query.count()

    click.echo(f"\n  DevTools Statistics")
    click.echo(f"  ──────────────────")
    click.echo(f"  Work Items:  {work_count}")
    click.echo(f"  Features:    {feature_count}")
    click.echo(f"  Scan Results: {scan_count}")
    click.echo(f"  Sessions:    {session_count}\n")


if __name__ == "__main__":
    cli()
