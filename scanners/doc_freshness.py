"""Doc Freshness Scanner — detect documentation that is stale relative to its source code.

Uses git log to compare the last-modified date of documentation files against
the source files they are supposed to track (configured in `watched_docs`).

Pure Python scanner — no Flask imports.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from scanners.base import ScanFinding, ScanOutput


class DocFreshnessScanner:
    """Scan for stale documentation by comparing git timestamps."""

    name = "doc_freshness"
    description = (
        "Detect documentation that hasn't been updated since its source code changed"
    )
    version = "1.0"

    def scan(self, project_config: dict) -> ScanOutput:
        """Scan watched docs for staleness.

        Args:
            project_config: Project config dict (must include watched_docs, project_root)

        Returns:
            ScanOutput with findings for stale docs
        """
        import time

        start = time.time()

        # Support both ProjectConfig objects and plain dicts
        if hasattr(project_config, "project_root"):
            project_root = Path(project_config.project_root)
            watched_docs = getattr(project_config, "watched_docs", [])
        else:
            project_root = Path(project_config.get("project_root", "."))
            watched_docs = project_config.get("watched_docs", [])

        if not watched_docs:
            return ScanOutput(
                findings=[], scanned_files=0, errors=["No watched_docs configured"]
            )

        findings = []
        errors = []
        scanned = 0

        for entry in watched_docs:
            # Support both WatchedDoc dataclass and plain dict
            if hasattr(entry, "doc"):
                doc_path = entry.doc
                watches = entry.watches
                priority = entry.priority
            else:
                doc_path = entry.get("doc", "")
                watches = entry.get("watches", [])
                priority = entry.get("priority", "medium")

            full_doc_path = project_root / doc_path

            if not full_doc_path.exists():
                errors.append(f"Doc not found: {doc_path}")
                continue

            scanned += 1

            # Get doc last-modified date from git
            doc_date = self._git_last_modified(project_root, doc_path)
            if doc_date is None:
                errors.append(f"Could not get git date for: {doc_path}")
                continue

            # Check each watched source path
            for watch_path in watches:
                source_date = self._git_last_modified_glob(project_root, watch_path)
                if source_date is None:
                    continue  # No git history for this path — skip silently

                if source_date > doc_date:
                    days_stale = (source_date - doc_date).days

                    # Map priority to severity
                    severity = self._priority_to_severity(priority)

                    findings.append(
                        ScanFinding(
                            file=doc_path,
                            line=None,
                            message=(
                                f"Doc '{doc_path}' is {days_stale}d stale — "
                                f"source '{watch_path}' was modified on "
                                f"{source_date.strftime('%Y-%m-%d')} "
                                f"but doc last updated {doc_date.strftime('%Y-%m-%d')}"
                            ),
                            severity=severity,
                            scanner=self.name,
                            details={
                                "doc_path": doc_path,
                                "source_path": watch_path,
                                "doc_date": doc_date.isoformat(),
                                "source_date": source_date.isoformat(),
                                "days_stale": days_stale,
                                "priority": priority,
                            },
                        )
                    )

        elapsed = int((time.time() - start) * 1000)

        return ScanOutput(
            findings=findings,
            scanned_files=scanned,
            errors=errors,
            duration_ms=elapsed,
        )

    def _git_last_modified(self, repo_root: Path, rel_path: str) -> datetime | None:
        """Get the last git commit date for a specific file.

        Args:
            repo_root: Root of the git repository
            rel_path: Path relative to repo root

        Returns:
            datetime of last commit, or None if not tracked
        """
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%aI", "--", rel_path],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return datetime.fromisoformat(result.stdout.strip())
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _git_last_modified_glob(
        self, repo_root: Path, path_pattern: str
    ) -> datetime | None:
        """Get the most recent git commit date across all files matching a path.

        Handles both single files and directories (e.g., 'routes/api/').

        Args:
            repo_root: Root of the git repository
            path_pattern: File or directory path relative to repo root

        Returns:
            datetime of most recent commit across all matching files, or None
        """
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%aI", "--", path_pattern],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return datetime.fromisoformat(result.stdout.strip())
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def _priority_to_severity(priority: str) -> str:
        """Map config priority to scanner severity."""
        mapping = {
            "critical": "critical",
            "high": "warning",
            "medium": "info",
            "low": "info",
        }
        return mapping.get(priority, "info")
