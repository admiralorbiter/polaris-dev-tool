"""Project configuration loader with validation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ManagedDoc:
    """A document that DevTools owns and exports."""

    path: str
    model: str
    format: str


@dataclass
class WatchedDoc:
    """A document DevTools checks for freshness."""

    doc: str
    watches: list[str]
    priority: str = "medium"


@dataclass
class ProjectConfig:
    """Validated project configuration."""

    project_name: str
    project_key: str
    project_root: Path
    paths: dict[str, str]
    conventions: dict
    managed_docs: dict[str, ManagedDoc] = field(default_factory=dict)
    watched_docs: list[WatchedDoc] = field(default_factory=list)
    freshness_weights: dict[str, float] = field(default_factory=dict)
    existing_tools: dict[str, str] = field(default_factory=dict)
    _config_path: Optional[str] = None

    def validate(self) -> list[str]:
        """Validate the config. Returns list of warnings (empty = valid).

        Raises:
            ValueError: If a fatal validation error is found.
        """
        warnings = []

        # Fatal: project_root must exist
        if not self.project_root.exists():
            raise ValueError(
                f"project_root does not exist: {self.project_root}"
            )

        if not self.project_root.is_dir():
            raise ValueError(
                f"project_root is not a directory: {self.project_root}"
            )

        # Warnings: paths should exist
        for key, rel_path in self.paths.items():
            full_path = self.project_root / rel_path
            if not full_path.exists():
                warnings.append(f"paths.{key} does not exist: {full_path}")

        # Warnings: managed doc parent dirs should exist
        for key, doc in self.managed_docs.items():
            parent = (self.project_root / doc.path).parent
            if not parent.exists():
                warnings.append(
                    f"managed_docs.{key} parent dir missing: {parent}"
                )

        # Warnings: watched docs should exist
        for wd in self.watched_docs:
            doc_path = self.project_root / wd.doc
            if not doc_path.exists():
                warnings.append(f"watched doc does not exist: {doc_path}")

        # Info: conventions should have auth_decorators
        if not self.conventions.get("auth_decorators"):
            warnings.append("conventions.auth_decorators is empty")

        return warnings

    def resolve_path(self, key: str) -> Path:
        """Resolve a paths.* key to an absolute path."""
        rel = self.paths.get(key, "")
        return self.project_root / rel


def _parse_managed_docs(raw: dict) -> dict[str, ManagedDoc]:
    """Parse managed_docs section from raw YAML."""
    if not raw:
        return {}
    result = {}
    for key, val in raw.items():
        result[key] = ManagedDoc(
            path=val["path"],
            model=val["model"],
            format=val["format"],
        )
    return result


def _parse_watched_docs(raw: list) -> list[WatchedDoc]:
    """Parse watched_docs section from raw YAML."""
    if not raw:
        return []
    return [
        WatchedDoc(
            doc=item["doc"],
            watches=item.get("watches", []),
            priority=item.get("priority", "medium"),
        )
        for item in raw
    ]


def load_project_config(yaml_path: str | Path) -> ProjectConfig:
    """Load a single project config from a YAML file.

    Args:
        yaml_path: Path to the YAML config file.

    Returns:
        Validated ProjectConfig instance.
    """
    yaml_path = Path(yaml_path)
    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    config = ProjectConfig(
        project_name=raw["project_name"],
        project_key=raw["project_key"],
        project_root=Path(raw["project_root"]),
        paths=raw.get("paths", {}),
        conventions=raw.get("conventions", {}),
        managed_docs=_parse_managed_docs(raw.get("managed_docs")),
        watched_docs=_parse_watched_docs(raw.get("watched_docs")),
        freshness_weights=raw.get("freshness_weights", {}),
        existing_tools=raw.get("existing_tools", {}),
        _config_path=str(yaml_path),
    )

    return config


def load_all_project_configs(
    projects_dir: str | Path = "projects",
) -> dict[str, ProjectConfig]:
    """Load all project configs from the projects directory.

    Args:
        projects_dir: Path to the directory containing YAML configs.

    Returns:
        Dict mapping project_key to ProjectConfig.

    Raises:
        ValueError: If duplicate project_keys are found.
    """
    projects_dir = Path(projects_dir)
    configs = {}

    if not projects_dir.exists():
        return configs

    for yaml_file in sorted(projects_dir.glob("*.yaml")):
        config = load_project_config(yaml_file)
        if config.project_key in configs:
            raise ValueError(
                f"Duplicate project_key '{config.project_key}' "
                f"in {yaml_file} and {configs[config.project_key]._config_path}"
            )
        configs[config.project_key] = config

    return configs
