"""Feature Doc Exporter — generate per-feature documentation pages.

Produces a markdown page for each Feature that has a doc_slug,
including metadata, implementation timeline, linked WorkItems,
and test coverage references.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from exporters.base import BaseExporter
from models import Feature


class FeatureDocExporter(BaseExporter):
    """Export per-feature documentation pages."""

    format_key = "feature_doc_v1"

    def render(self, project: str, project_config=None) -> str:
        """Render all features with doc_slugs as a combined document.

        For the sync pipeline, this exports all feature docs at once.
        Each feature is separated by a horizontal rule.

        Args:
            project: Project key to filter Features.
            project_config: Optional project config.

        Returns:
            Combined markdown string (for preview/single-file mode).
        """
        features = (
            Feature.query.filter_by(project=project)
            .filter(Feature.doc_slug.isnot(None))
            .order_by(Feature.domain, Feature.requirement_id)
            .all()
        )

        if not features:
            return "*No features with doc_slug configured.*\n"

        parts = []
        for feature in features:
            parts.append(self.render_feature(feature))
            parts.append("\n---\n")

        return "\n".join(parts)

    def render_feature(self, feature) -> str:
        """Render a single feature's documentation page.

        Args:
            feature: Feature model instance.

        Returns:
            Markdown string for this feature.
        """
        export_time = datetime.now(timezone.utc)
        lines = []

        # Header
        lines.append(self.auto_generated_notice(export_time))
        lines.append("")
        lines.append(self.header(feature.name))
        lines.append("")

        # Metadata table
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        if feature.requirement_id:
            lines.append(f"| **Requirement ID** | `{feature.requirement_id}` |")
        if feature.domain:
            lines.append(f"| **Domain** | {feature.domain} |")
        lines.append(f"| **Status** | {feature.status or 'requested'} |")
        lines.append(
            f"| **Implementation** | {feature.implementation_status or 'pending'} |"
        )
        if feature.date_requested:
            lines.append(f"| **Requested** | {feature.date_requested.isoformat()} |")
        if feature.date_shipped:
            lines.append(f"| **Shipped** | {feature.date_shipped.isoformat()} |")
        if feature.next_review:
            lines.append(f"| **Next Review** | {feature.next_review.isoformat()} |")
        lines.append("")

        # Test coverage
        test_cases = feature.get_test_cases()
        if test_cases:
            lines.append(self.header("Test Coverage", 2))
            lines.append("")
            for tc in test_cases:
                lines.append(f"- `{tc}`")
            lines.append("")

        # Related WorkItems
        work_items = feature.work_items if hasattr(feature, "work_items") else []
        if work_items:
            lines.append(self.header("Related Work Items", 2))
            lines.append("")
            lines.append("| ID | Title | Status | Category |")
            lines.append("|----|-------|--------|----------|")
            for wi in work_items:
                sid = wi.source_id or str(wi.id)
                lines.append(f"| {sid} | {wi.title} | {wi.status} | {wi.category} |")
            lines.append("")

        # Notes
        if feature.notes:
            lines.append(self.header("Notes", 2))
            lines.append("")
            lines.append(feature.notes)
            lines.append("")

        return "\n".join(lines)

    def export(self, project, output_path, project_config=None):
        """Export all feature docs to individual files.

        Args:
            project: Project key.
            output_path: Base directory for feature docs.
            project_config: Optional project config.

        Returns:
            Dict with export stats.
        """
        features = (
            Feature.query.filter_by(project=project)
            .filter(Feature.doc_slug.isnot(None))
            .order_by(Feature.domain, Feature.requirement_id)
            .all()
        )

        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        exported = 0
        for feature in features:
            content = self.render_feature(feature)
            file_path = output_dir / f"{feature.doc_slug}.md"
            self.write_file(content, file_path)
            exported += 1

        # Record export
        self.record_export(
            project=project,
            target="feature_docs",
            file_path=str(output_path),
            record_count=exported,
        )

        return {"exported": exported, "file": str(output_path)}

    @staticmethod
    def slugify(name: str) -> str:
        """Generate a URL-friendly slug from a feature name.

        Args:
            name: Feature name like "Draft Review Queue"

        Returns:
            Slug like "draft-review-queue"
        """
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
