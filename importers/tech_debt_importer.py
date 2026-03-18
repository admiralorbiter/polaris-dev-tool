"""Tech Debt Importer — parse VMS tech_debt.md into WorkItem records.

Handles three sections:
1. Active items (## TD-xxx: Title headers with body text)
2. Priority table (| Priority | ID | Item | Effort |)
3. Resolved archive (| ID | Title | Resolved | Summary |)
"""

import re
from datetime import datetime
from pathlib import Path

from models import db, WorkItem


class TechDebtImporter:
    """Parse tech_debt.md and create/update WorkItem records."""

    # Regex patterns — match the TD-xxx ID then grab everything after the ':'
    ITEM_HEADER = re.compile(r"^##\s+(TD-\d+):\s+(.+)$")
    METADATA_LINE = re.compile(
        r"\*\*Created:\*\*\s*([\d-]+)"
        r"(?:\s*·\s*\*\*(?:Priority|Evaluated):\*\*\s*(\w+))?"
        r"(?:\s*·\s*\*\*Category:\*\*\s*(.+))?"
    )
    PRIORITY_TABLE_ROW = re.compile(
        r"\|\s*~~?\d+~~?\s*\|\s*(?:~~)?\*\*(TD-\d+)\*\*(?:~~)?\s*\|"
        r"\s*(?:~~)?(.+?)(?:~~)?\s*(?:✅[^|]*)?\|\s*(?:~~)?(\w+)(?:~~)?\s*\|"
    )
    RESOLVED_TABLE_ROW = re.compile(
        r"\|\s*(TD-\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|"
    )

    def import_from_file(self, file_path: str | Path, project: str = "vms") -> dict:
        """Parse tech_debt.md and create WorkItem records.

        Args:
            file_path: Path to tech_debt.md
            project: Project key for WorkItem records

        Returns:
            Dict with counts: created, updated, skipped, errors
        """
        file_path = Path(file_path)
        lines = file_path.read_text(encoding="utf-8").splitlines()

        # Parse all sections
        active_items = self._parse_active_items(lines)
        priority_data = self._parse_priority_table(lines)
        resolved_items = self._parse_resolved_archive(lines)

        # Merge priority data into active items
        for source_id, pdata in priority_data.items():
            if source_id in active_items:
                if pdata.get("effort"):
                    active_items[source_id]["effort"] = pdata["effort"]
                if pdata.get("priority_rank"):
                    active_items[source_id]["priority_rank"] = pdata["priority_rank"]

        # Persist
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

        for source_id, data in active_items.items():
            try:
                self._upsert_work_item(project, source_id, data, is_archived=False)
                stats["created"] += 1
            except Exception as e:
                stats["errors"].append(f"{source_id}: {e}")

        for source_id, data in resolved_items.items():
            try:
                self._upsert_work_item(project, source_id, data, is_archived=True)
                stats["created"] += 1
            except Exception as e:
                stats["errors"].append(f"{source_id}: {e}")

        db.session.commit()
        return stats

    def _parse_active_items(self, lines: list[str]) -> dict:
        """Parse active tech debt items from ## headers."""
        items = {}
        current_id = None
        current_data = None
        in_resolved = False
        in_priority = False
        body_lines = []

        for line in lines:
            stripped = line.strip()

            # Detect section boundaries
            if stripped.startswith("## Priority Order"):
                if current_id and current_data:
                    current_data["notes"] = "\n".join(body_lines).strip()
                    items[current_id] = current_data
                in_priority = True
                current_id = None
                continue

            if stripped.startswith("## Resolved Archive"):
                if current_id and current_data:
                    current_data["notes"] = "\n".join(body_lines).strip()
                    items[current_id] = current_data
                in_resolved = True
                current_id = None
                continue

            if in_resolved or in_priority:
                # But check if this is a new TD heading — reset section flags
                if self.ITEM_HEADER.match(stripped):
                    in_resolved = False
                    in_priority = False
                    # Fall through to the header matching below
                else:
                    continue

            # Match item headers
            match = self.ITEM_HEADER.match(stripped)
            if match:
                # Save previous item
                if current_id and current_data:
                    current_data["notes"] = "\n".join(body_lines).strip()
                    items[current_id] = current_data

                source_id = match.group(1)
                raw_title = match.group(2).strip()

                # Detect status from title suffixes
                status = "backlog"
                if "✅ RESOLVED" in raw_title or "✅" in raw_title:
                    status = "done"
                elif "*(Deferred)*" in raw_title:
                    status = "deferred"

                # Clean the title: remove status markers
                title = raw_title
                title = re.sub(r"\s*✅\s*RESOLVED\s*$", "", title)
                title = re.sub(r"\s*\*\(Deferred\)\*\s*$", "", title)
                title = title.strip()

                current_id = source_id
                current_data = {
                    "title": title,
                    "status": status,
                    "category": "tech_debt",
                }
                body_lines = []
                continue

            # Match metadata lines
            if current_id:
                meta_match = self.METADATA_LINE.search(stripped)
                if meta_match:
                    if meta_match.group(1):
                        try:
                            current_data["created"] = datetime.strptime(
                                meta_match.group(1), "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            pass
                    if meta_match.group(2):
                        current_data["priority"] = meta_match.group(2).lower()
                    if meta_match.group(3):
                        current_data["category_detail"] = meta_match.group(3).strip()
                else:
                    body_lines.append(line)

        # Don't forget the last item
        if current_id and current_data:
            current_data["notes"] = "\n".join(body_lines).strip()
            items[current_id] = current_data

        return items

    def _parse_priority_table(self, lines: list[str]) -> dict:
        """Parse the Priority Order table."""
        priority_data = {}
        in_section = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("## Priority Order"):
                in_section = True
                continue

            if in_section and stripped.startswith("## "):
                break

            if in_section:
                match = self.PRIORITY_TABLE_ROW.search(stripped)
                if match:
                    source_id = match.group(1)
                    effort = match.group(3).strip()
                    priority_data[source_id] = {"effort": effort}

        return priority_data

    def _parse_resolved_archive(self, lines: list[str]) -> dict:
        """Parse the Resolved Archive table."""
        resolved = {}
        in_section = False
        past_header = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("## Resolved Archive"):
                in_section = True
                continue

            if in_section and stripped.startswith("## "):
                break

            if in_section:
                # Skip table header and separator
                if stripped.startswith("| ID") or stripped.startswith("|--"):
                    past_header = True
                    continue

                if past_header and stripped.startswith("|"):
                    match = self.RESOLVED_TABLE_ROW.match(stripped)
                    if match:
                        source_id = match.group(1).strip()
                        title = match.group(2).strip()
                        resolved_date = match.group(3).strip()
                        summary = match.group(4).strip()

                        resolved[source_id] = {
                            "title": title,
                            "status": "done",
                            "category": "tech_debt",
                            "resolution_summary": summary,
                        }

                        # Parse resolved date
                        try:
                            resolved[source_id]["completed_date"] = datetime.strptime(
                                resolved_date, "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            pass

        return resolved

    def _upsert_work_item(
        self,
        project: str,
        source_id: str,
        data: dict,
        is_archived: bool,
    ):
        """Create or update a WorkItem."""
        existing = WorkItem.query.filter_by(source_id=source_id).first()

        if existing:
            # Update
            existing.title = data.get("title", existing.title)
            existing.status = data.get("status", existing.status)
            existing.priority = data.get("priority", existing.priority)
            existing.effort = data.get("effort", existing.effort)
            existing.notes = data.get("notes", existing.notes)
            existing.resolution_summary = data.get(
                "resolution_summary", existing.resolution_summary
            )
            existing.is_archived = is_archived
        else:
            # Create
            item = WorkItem(
                project=project,
                source_id=source_id,
                title=data.get("title", ""),
                category=data.get("category", "tech_debt"),
                priority=data.get("priority", "medium"),
                effort=data.get("effort"),
                status=data.get("status", "backlog"),
                notes=data.get("notes"),
                resolution_summary=data.get("resolution_summary"),
                is_archived=is_archived,
                identified_date=data.get("created"),
                completed_at=(
                    datetime.combine(data["completed_date"], datetime.min.time())
                    if data.get("completed_date")
                    else None
                ),
            )
            db.session.add(item)
