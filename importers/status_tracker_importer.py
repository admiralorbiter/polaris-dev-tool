"""Status Tracker Importer — parse VMS development_status_tracker.md into Feature records.

File format:
- ## Domain Name (e.g., "## Virtual Events", "## In-Person Events")
- ### Subsection (e.g., "### Core Virtual Event Management")
- Rows: | FR-xxx-nnn | requirement text | ✅ | notes |
- Status symbols: ✅ 🔧 📋 🔮 ➖
"""

import re
from pathlib import Path

from models import db, Feature


# Map status symbol → implementation_status value
SYMBOL_MAP = {
    "✅": "implemented",
    "🔧": "partial",
    "📋": "pending",
    "🔮": "future",
    "➖": "na",
}


class StatusTrackerImporter:
    """Parse development_status_tracker.md and create/update Feature records."""

    # Match FR-xxx-nnn rows in tables
    ROW_RE = re.compile(r"\|\s*(FR-[\w-]+)\s*\|\s*(.+?)\s*\|\s*(\S+)\s*\|\s*(.*?)\s*\|")

    # Match ## Domain headings (skip "Status Legend", "Quick Summary")
    DOMAIN_RE = re.compile(r"^##\s+(.+)$")
    SKIP_DOMAINS = {"Status Legend", "Quick Summary"}

    # Match ### Subsection headings
    SUBSECTION_RE = re.compile(r"^###\s+(.+)$")

    # Extract test case references from notes
    TC_RE = re.compile(r"TC-\d+(?:–TC-\d+|[–,]\s*TC-\d+)*")

    def import_from_file(self, file_path: str | Path, project: str = "vms") -> dict:
        """Parse development_status_tracker.md and create Feature records.

        Args:
            file_path: Path to development_status_tracker.md
            project: Project key for Feature records

        Returns:
            Dict with counts: created, updated, skipped, errors
        """
        file_path = Path(file_path)
        lines = file_path.read_text(encoding="utf-8").splitlines()

        features = self._parse_features(lines)

        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

        for data in features:
            try:
                created = self._upsert_feature(project, data)
                if created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
            except Exception as e:
                stats["errors"].append(f"{data.get('requirement_id', '?')}: {e}")

        db.session.commit()
        return stats

    def _parse_features(self, lines: list[str]) -> list[dict]:
        """Parse all FR rows from the status tracker."""
        features = []
        current_domain = None
        in_skip_section = False

        for line in lines:
            stripped = line.strip()

            # Check for ## domain headings
            domain_match = self.DOMAIN_RE.match(stripped)
            if domain_match:
                domain_name = domain_match.group(1).strip()
                if domain_name in self.SKIP_DOMAINS:
                    in_skip_section = True
                    current_domain = None
                    continue
                in_skip_section = False
                current_domain = domain_name
                continue

            if in_skip_section:
                continue

            # Parse FR rows
            row_match = self.ROW_RE.match(stripped)
            if row_match and current_domain:
                req_id = row_match.group(1).strip()
                name = row_match.group(2).strip()
                symbol = row_match.group(3).strip()
                notes = row_match.group(4).strip()

                impl_status = SYMBOL_MAP.get(symbol, "pending")

                # Extract test case references
                test_cases = []
                tc_matches = self.TC_RE.findall(notes)
                for tc_match in tc_matches:
                    # Expand ranges like TC-130–TC-140 into individual refs
                    test_cases.append(tc_match)

                # Determine lifecycle status from implementation
                if impl_status == "implemented":
                    status = "shipped"
                elif impl_status == "partial":
                    status = "in_progress"
                elif impl_status == "future":
                    status = "requested"
                else:
                    status = "requested"

                features.append(
                    {
                        "requirement_id": req_id,
                        "name": name,
                        "domain": current_domain,
                        "implementation_status": impl_status,
                        "status": status,
                        "test_cases": test_cases,
                        "notes": notes if notes else None,
                    }
                )

        return features

    def _upsert_feature(self, project: str, data: dict) -> bool:
        """Create or update a Feature record.

        Returns True if created, False if updated.
        """
        existing = Feature.query.filter_by(
            requirement_id=data["requirement_id"]
        ).first()

        if existing:
            existing.name = data["name"]
            existing.domain = data["domain"]
            existing.implementation_status = data["implementation_status"]
            existing.status = data["status"]
            if data["test_cases"]:
                existing.set_test_cases(data["test_cases"])
            if data["notes"]:
                existing.notes = data["notes"]
            return False
        else:
            feature = Feature(
                project=project,
                requirement_id=data["requirement_id"],
                name=data["name"],
                domain=data["domain"],
                implementation_status=data["implementation_status"],
                status=data["status"],
                notes=data.get("notes"),
            )
            if data["test_cases"]:
                feature.set_test_cases(data["test_cases"])
            db.session.add(feature)
            return True
