"""Scanner protocol and shared data structures."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ScanFinding:
    """A single finding from a scanner."""

    file: str
    line: int | None
    message: str
    severity: str  # "critical", "warning", "info"
    scanner: str  # e.g., "coupling"
    details: dict | None = None


@dataclass
class ScanOutput:
    """Complete output from a scanner run."""

    findings: list[ScanFinding] = field(default_factory=list)
    scanned_files: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "info")


class Scanner(Protocol):
    """Protocol that all scanners must implement."""

    name: str
    description: str
    version: str

    def scan(self, project_config: dict) -> ScanOutput: ...


# Scanner registry — populated by scanner modules
SCANNER_REGISTRY: dict[str, type] = {}
