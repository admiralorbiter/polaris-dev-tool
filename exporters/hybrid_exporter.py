"""Hybrid Doc Exporter — fill slot markers in authored templates with DB content.

Templates contain authored prose plus `<!-- devtools:slot:name -->` markers.
The exporter replaces content between slot markers with DB-rendered output
while leaving everything else untouched.

Slot marker format:
    <!-- devtools:slot:SLOT_NAME -->
    (existing content replaced on each export)
    <!-- /devtools:slot -->
"""

import re
from pathlib import Path

from exporters.base import BaseExporter
from models import WorkItem, ScanResult


# Regex to match slot blocks
SLOT_PATTERN = re.compile(
    r"(<!-- devtools:slot:(\w+) -->)"  # opening marker (group 1=full, 2=name)
    r"(.*?)"  # existing content (group 3, lazy)
    r"(<!-- /devtools:slot -->)",  # closing marker (group 4)
    re.DOTALL,
)


class HybridDocExporter(BaseExporter):
    """Export hybrid docs by filling slot markers in template files."""

    format_key = "hybrid_v1"

    def extract_slots(self, template_text):
        """Find all slot markers in a template.

        Args:
            template_text: The raw template content.

        Returns:
            List of dicts with 'name', 'start', 'end', 'existing_content'.
        """
        slots = []
        for match in SLOT_PATTERN.finditer(template_text):
            slots.append(
                {
                    "name": match.group(2),
                    "existing_content": match.group(3),
                    "full_match": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
        return slots

    def render_slot(self, slot_name, project):
        """Render a single slot by name.

        Args:
            slot_name: The slot identifier (e.g., 'recent_changes').
            project: Project key.

        Returns:
            Rendered markdown string for the slot content.
        """
        renderers = {
            "recent_changes": self._render_recent_changes,
            "route_table": self._render_route_table,
        }
        renderer = renderers.get(slot_name)
        if renderer is None:
            return f"\n*Unknown slot: {slot_name}*\n"
        return renderer(project)

    def render(self, project, template_text, project_config=None):
        """Fill all slots in a template with DB-rendered content.

        Args:
            project: Project key.
            template_text: The raw template content with slot markers.
            project_config: Optional project config.

        Returns:
            Template with slot content replaced.
        """

        def replace_slot(match):
            open_marker = match.group(1)
            slot_name = match.group(2)
            close_marker = match.group(4)
            content = self.render_slot(slot_name, project)
            return f"{open_marker}\n{content}\n{close_marker}"

        return SLOT_PATTERN.sub(replace_slot, template_text)

    def export(self, project, output_path, project_config=None, template_path=None):
        """Read template, fill slots, write output.

        Args:
            project: Project key.
            output_path: Where to write the filled doc.
            project_config: Optional project config.
            template_path: Path to the template file with slot markers.
                          If None, reads from output_path itself (in-place).

        Returns:
            Dict with export stats.
        """
        source = Path(template_path) if template_path else Path(output_path)
        template_text = source.read_text(encoding="utf-8")

        filled = self.render(project, template_text, project_config)
        self.write_file(filled, Path(output_path))

        # Count slots filled
        slots = self.extract_slots(template_text)

        self.record_export(project, "hybrid", str(output_path), len(slots))

        return {
            "file": str(output_path),
            "slots_filled": len(slots),
            "slot_names": [s["name"] for s in slots],
        }

    # ── Slot Renderers ──────────────────────────────────────────

    def _render_recent_changes(self, project, limit=10):
        """Render recent completed work items as a bullet list.

        Groups by category (features, bugs, tech debt) and shows at most
        `limit` items total.
        """
        items = (
            WorkItem.query.filter_by(project=project, status="done")
            .order_by(WorkItem.updated_at.desc())
            .limit(limit)
            .all()
        )

        if not items:
            return "*No recent changes.*"

        from collections import OrderedDict

        CATEGORIES = OrderedDict(
            [
                ("feature", "Features"),
                ("bug", "Bug Fixes"),
                ("tech_debt", "Tech Debt"),
            ]
        )

        by_cat = {}
        for item in items:
            cat = item.category or "feature"
            by_cat.setdefault(cat, []).append(item)

        lines = []
        for cat_key, cat_label in CATEGORIES.items():
            cat_items = by_cat.pop(cat_key, [])
            if cat_items:
                lines.append(f"**{cat_label}**")
                for item in cat_items:
                    sid = f"**{item.source_id}** " if item.source_id else ""
                    lines.append(f"- {sid}{item.title}")
                lines.append("")

        # Any remaining categories
        for cat_key, cat_items in by_cat.items():
            lines.append(f"**{cat_key.replace('_', ' ').title()}**")
            for item in cat_items:
                sid = f"**{item.source_id}** " if item.source_id else ""
                lines.append(f"- {sid}{item.title}")
            lines.append("")

        return "\n".join(lines).rstrip()

    def _render_route_table(self, project):
        """Render a route table from the latest coupling scan results.

        Uses `ScanResult` records to extract route information.
        """
        scan = (
            ScanResult.query.filter_by(project=project, scanner="coupling")
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )

        if not scan:
            return "*No scan data available. Run a scan first.*"

        results = scan.get_results()
        if not results:
            return "*No routes found in scan results.*"

        # Build route table from scan findings
        routes = []
        for finding in results:
            if isinstance(finding, dict):
                file_path = finding.get("file", "")
                message = finding.get("message", "")
                routes.append(
                    {
                        "file": file_path,
                        "detail": message,
                    }
                )

        if not routes:
            return "*No route data in scan findings.*"

        lines = []
        lines.append("| File | Detail |")
        lines.append("| --- | --- |")
        for r in routes[:30]:  # cap at 30 to avoid huge tables
            lines.append(f"| `{r['file']}` | {r['detail']} |")

        return "\n".join(lines)
