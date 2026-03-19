"""Status Tracker Exporter — render Features back to VMS status tracker format.

Produces a markdown file matching the VMS structure:
1. Header with metadata
2. Status legend
3. Quick summary table (auto-computed)
4. Domain sections with subsection tables
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from exporters.base import BaseExporter
from models import Feature


# Status symbol mapping (implementation_status → emoji)
STATUS_SYMBOLS = {
    "implemented": "✅",
    "partial": "🔧",
    "pending": "📋",
    "future": "🔮",
    "na": "➖",
}


class StatusTrackerExporter(BaseExporter):
    """Export Features to development_status_tracker.md format."""

    format_key = "status_tracker_v1"

    def render(self, project: str, project_config=None) -> str:
        """Render all Features to the status tracker markdown format.

        Args:
            project: Project key to filter Features
            project_config: Optional project config

        Returns:
            Full markdown string
        """
        export_time = datetime.utcnow()

        # Query all features, ordered by domain then requirement_id
        features = (
            Feature.query.filter_by(project=project)
            .order_by(Feature.domain, Feature.requirement_id)
            .all()
        )

        # Group by domain
        domains = defaultdict(list)
        for f in features:
            domains[f.domain or "Uncategorized"].append(f)

        parts = []

        # Auto-generated notice
        parts.append(self.auto_generated_notice(export_time))
        parts.append("")

        # Header
        parts.append(self.header("VMS Development Status Tracker"))
        parts.append("")
        parts.append(f"**Last Updated:** {export_time.strftime('%B %Y')}")
        parts.append(f"**Total Functional Requirements:** ~{len(features)}")
        parts.append("")
        parts.append("---")
        parts.append("")

        # Status legend
        parts.append(self._render_legend())
        parts.append("")
        parts.append("---")
        parts.append("")

        # Quick summary table
        parts.append(self._render_summary_table(domains))
        parts.append("")
        parts.append("---")
        parts.append("")

        # Domain sections
        for domain_name in sorted(domains.keys()):
            domain_features = domains[domain_name]
            parts.append(self._render_domain(domain_name, domain_features))
            parts.append("")
            parts.append("---")
            parts.append("")

        return "\n".join(parts)

    def export(self, project: str, output_path: Path, project_config=None) -> dict:
        """Render and write status tracker to file.

        Returns:
            Dict with export stats
        """
        content = self.render(project, project_config)

        total = Feature.query.filter_by(project=project).count()

        # Write file
        self.write_file(content, output_path)

        # Record export
        self.record_export(
            project=project,
            target="status_tracker",
            file_path=str(output_path),
            record_count=total,
        )

        # Count by status
        implemented = Feature.query.filter_by(
            project=project, implementation_status="implemented"
        ).count()
        partial = Feature.query.filter_by(
            project=project, implementation_status="partial"
        ).count()
        pending = Feature.query.filter_by(
            project=project, implementation_status="pending"
        ).count()

        return {
            "total": total,
            "implemented": implemented,
            "partial": partial,
            "pending": pending,
            "file": str(output_path),
        }

    def _render_legend(self) -> str:
        """Render the status legend table."""
        lines = [
            self.header("Status Legend", 2),
            "",
            "| Symbol | Meaning |",
            "|--------|---------|",
            "| ✅ | **Implemented** — Has test coverage (TC-xxx) |",
            "| 🔧 | **Partial** — Partially implemented or needs enhancement |",
            "| 📋 | **Pending** — TBD, not yet implemented |",
            "| 🔮 | **Future** — Phase 5, Near-term, or Placeholder |",
            "| ➖ | **N/A** — Implicit/contextual, no explicit testing needed |",
        ]
        return "\n".join(lines)

    def _render_summary_table(self, domains: dict[str, list]) -> str:
        """Render the quick summary table with auto-computed counts."""
        lines = [
            self.header("Quick Summary", 2),
            "",
            "| Domain | Total | ✅ | 🔧 | 📋 | 🔮 |",
            "|--------|-------|-----|-----|-----|-----|",
        ]

        for domain_name in sorted(domains.keys()):
            features = domains[domain_name]
            total = len(features)
            counts = defaultdict(int)
            for f in features:
                counts[f.implementation_status] += 1

            # Create anchor link
            anchor = (
                domain_name.lower()
                .replace(" ", "-")
                .replace("&", "")
                .replace("  ", "-")
            )
            lines.append(
                f"| [{domain_name}](#{anchor}) "
                f"| {total} "
                f"| {counts.get('implemented', 0)} "
                f"| {counts.get('partial', 0)} "
                f"| {counts.get('pending', 0)} "
                f"| {counts.get('future', 0)} |"
            )

        return "\n".join(lines)

    def _render_domain(self, domain_name: str, features: list) -> str:
        """Render a single domain section with its features."""
        lines = [self.header(domain_name, 2), ""]

        # Group by subsection (using notes or a simple heuristic)
        # For now, render all features in one table per domain
        lines.append("| ID | Requirement | Status | Notes |")
        lines.append("|----|-------------|--------|-------|")

        for f in features:
            symbol = STATUS_SYMBOLS.get(f.implementation_status, "❓")
            notes = self._format_notes(f)
            lines.append(f"| {f.requirement_id} | {f.name} | {symbol} | {notes} |")

        return "\n".join(lines)

    def _format_notes(self, feature) -> str:
        """Format notes for a feature row."""
        parts = []

        # Include test cases if present
        test_cases = feature.get_test_cases()
        if test_cases:
            parts.append(", ".join(test_cases))

        # Include any other notes (without test cases)
        if feature.notes:
            # Strip out test case references already included
            note_text = feature.notes
            for tc in test_cases:
                note_text = note_text.replace(tc, "").strip(", ")
            note_text = note_text.strip()
            if note_text:
                parts.append(note_text)

        return ", ".join(parts) if parts else ""
