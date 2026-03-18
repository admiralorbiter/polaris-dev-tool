"""Tech Debt Exporter — render WorkItems back to VMS tech_debt.md format.

Produces a markdown file matching the VMS structure:
1. Header with description
2. Active items (## TD-xxx: Title headers)
3. Priority table
4. Resolved archive table
"""

from datetime import datetime
from pathlib import Path

from exporters.base import BaseExporter
from models import WorkItem


class TechDebtExporter(BaseExporter):
    """Export WorkItems to tech_debt.md format."""

    format_key = "tech_debt"

    def render(self, project: str, project_config=None) -> str:
        """Render all tech debt WorkItems to markdown.

        Args:
            project: Project key to filter WorkItems
            project_config: Optional project config (for path resolution)

        Returns:
            Full markdown string
        """
        export_time = datetime.utcnow()

        # Query items
        active_items = (
            WorkItem.query.filter_by(
                project=project, category="tech_debt", is_archived=False
            )
            .order_by(WorkItem.source_id)
            .all()
        )
        resolved_items = (
            WorkItem.query.filter_by(
                project=project, category="tech_debt", is_archived=True
            )
            .order_by(WorkItem.source_id)
            .all()
        )

        parts = []

        # Auto-generated notice
        parts.append(self.auto_generated_notice(export_time))
        parts.append("")

        # Header
        parts.append(self.header("Tech Debt Tracker"))
        parts.append("")
        parts.append(
            "This document tracks active technical debt. Resolved items are "
            "summarized in the [Resolved Archive](#resolved-archive) at the "
            "bottom. For the phased plan to address these items, see the "
            "[Development Plan](development_plan.md)."
        )
        parts.append("")
        parts.append("---")
        parts.append("")

        # Active items
        for item in active_items:
            parts.append(self._render_active_item(item))
            parts.append("")

        # Priority table
        if active_items:
            parts.append(self._render_priority_table(active_items))
            parts.append("")

        # Resolved archive
        if resolved_items:
            parts.append(self._render_resolved_archive(resolved_items))
            parts.append("")

        return "\n".join(parts)

    def export(self, project: str, output_path: Path, project_config=None) -> dict:
        """Render and write tech debt to file.

        Returns:
            Dict with export stats
        """
        content = self.render(project, project_config)

        active_count = WorkItem.query.filter_by(
            project=project, category="tech_debt", is_archived=False
        ).count()
        resolved_count = WorkItem.query.filter_by(
            project=project, category="tech_debt", is_archived=True
        ).count()
        total = active_count + resolved_count

        # Write file
        self.write_file(content, output_path)

        # Record export
        self.record_export(
            project=project,
            target="tech_debt",
            file_path=str(output_path),
            record_count=total,
        )

        return {
            "active": active_count,
            "resolved": resolved_count,
            "total": total,
            "file": str(output_path),
        }

    def _render_active_item(self, item: WorkItem) -> str:
        """Render a single active tech debt item."""
        lines = []

        # Header
        title = item.title
        if item.status == "deferred":
            lines.append(f"## {item.source_id}: {title} *(Deferred)*")
        else:
            lines.append(f"## {item.source_id}: {title}")

        lines.append("")

        # Metadata line
        meta_parts = []
        if item.identified_date:
            meta_parts.append(
                f"**Created:** {item.identified_date.strftime('%Y-%m-%d')}"
            )
        if item.priority and item.priority != "medium":
            meta_parts.append(f"**Priority:** {item.priority.capitalize()}")
        if meta_parts:
            lines.append(" · ".join(meta_parts))
            lines.append("")

        # Notes / body
        if item.notes:
            lines.append(item.notes)

        lines.append("")
        lines.append("---")

        return "\n".join(lines)

    def _render_priority_table(self, items: list[WorkItem]) -> str:
        """Render the priority order table."""
        lines = []
        lines.append("## Priority Order")
        lines.append("")
        lines.append("Ordered by **what best unblocks future work**:")
        lines.append("")

        headers = ["Priority", "ID", "Item", "Effort"]
        rows = []

        # Sort by priority rank if available, otherwise by source_id
        sorted_items = sorted(
            [i for i in items if i.status != "deferred"],
            key=lambda x: (x.source_id or ""),
        )

        for idx, item in enumerate(sorted_items, 1):
            effort = item.effort or "M"
            if item.status == "done":
                rows.append(
                    [
                        f"~~{idx}~~",
                        f"~~**{item.source_id}**~~",
                        f"~~{item.title}~~ ✅",
                        f"~~{effort}~~",
                    ]
                )
            else:
                rows.append(
                    [
                        str(idx),
                        f"**{item.source_id}**",
                        item.title,
                        effort,
                    ]
                )

        lines.append(self.table(headers, rows))

        # Add deferred note if any
        deferred = [i for i in items if i.status == "deferred"]
        if deferred:
            lines.append("")
            for item in deferred:
                lines.append(f"> {item.source_id} is intentionally deferred.")

        return "\n".join(lines)

    def _render_resolved_archive(self, items: list[WorkItem]) -> str:
        """Render the resolved archive table."""
        lines = []
        lines.append("---")
        lines.append("")
        lines.append("## Resolved Archive")
        lines.append("")
        lines.append("All resolved items, for historical reference:")
        lines.append("")

        headers = ["ID", "Title", "Resolved", "Summary"]
        rows = []

        for item in sorted(items, key=lambda x: (x.source_id or "")):
            resolved_date = (
                item.completed_at.strftime("%Y-%m-%d") if item.completed_at else "N/A"
            )
            summary = item.resolution_summary or "—"
            rows.append([item.source_id, item.title, resolved_date, summary])

        lines.append(self.table(headers, rows))

        return "\n".join(lines)
