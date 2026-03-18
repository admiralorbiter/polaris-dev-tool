"""AI Context Packet formatter — generates copy-paste-ready context for AI assistants.

Takes scan findings and formats them with problem, location, context,
suggested fix, and relevant code snippets so users can paste them into
any AI assistant for help resolving issues.
"""

from pathlib import Path

# Scanner-specific context templates
SCANNER_CONTEXT = {
    "coupling": {
        "purpose": (
            "The coupling scanner uses Python AST analysis to verify that "
            "every render_template() call references a template that exists on disk, "
            "and that every template file is referenced by at least one route."
        ),
        "fix_guidance": {
            "critical": (
                "This template is referenced in code but doesn't exist on disk. "
                "Either create the missing template or fix the render_template() call."
            ),
            "warning": (
                "This template exists on disk but no route references it via "
                "render_template(). It may be used via {% extends %}, {% include %}, "
                "or error handlers — if so, add it to the scanner's ignore list. "
                "If truly unused, delete it."
            ),
        },
    },
    "security": {
        "purpose": (
            "The security scanner checks that all Flask routes have authentication "
            "decorators (login_required, admin_required, etc.). Routes without auth "
            "decorators are flagged — POST/PUT/DELETE as critical, GET as warning."
        ),
        "fix_guidance": {
            "critical": (
                "This mutating route (POST/PUT/DELETE/PATCH) has no authentication "
                "decorator. Add @login_required or another auth decorator. If this "
                "route is intentionally public (e.g., login, webhook), add it to "
                "intentionally_public_routes in the project config."
            ),
            "warning": (
                "This GET route has no authentication decorator. Add @login_required "
                "if it should be protected. If it's intentionally public, add it to "
                "intentionally_public_routes in the project config."
            ),
        },
    },
}


def format_finding_context(
    finding: dict,
    scanner_name: str,
    project_root: str | None = None,
    snippet_lines: int = 5,
) -> str:
    """Format a single finding as an AI-ready context block.

    Args:
        finding: Finding dict from scan output.
        scanner_name: Name of the scanner that produced this finding.
        project_root: Absolute path to the project root (for reading source).
        snippet_lines: Number of lines of context around the finding.

    Returns:
        Formatted string ready to copy-paste to an AI assistant.
    """
    severity = finding.get("severity", "info").upper()
    file_path = finding.get("file", "unknown")
    line = finding.get("line")
    message = finding.get("message", "")
    details = finding.get("details") or {}

    # Build the context block
    parts = []

    # ── Problem ──
    parts.append(f"## {severity}: {message}")
    parts.append("")

    # ── Location ──
    parts.append("### Location")
    parts.append(f"- **File:** `{file_path}`" + (f" (line {line})" if line else ""))
    if details.get("blueprint"):
        parts.append(f"- **Blueprint:** `{details['blueprint']}`")
    if details.get("function_name"):
        parts.append(f"- **Function:** `{details['function_name']}()`")
    if details.get("url_pattern"):
        parts.append(f"- **URL:** `{details['url_pattern']}`")
    if details.get("methods"):
        parts.append(f"- **Methods:** {', '.join(details['methods'])}")
    parts.append("")

    # ── Scanner Context ──
    ctx = SCANNER_CONTEXT.get(scanner_name, {})
    if ctx.get("purpose"):
        parts.append("### Context")
        parts.append(ctx["purpose"])
        parts.append("")

    # ── Suggested Fix ──
    fix = ctx.get("fix_guidance", {}).get(finding.get("severity", "info"))
    if fix:
        parts.append("### Suggested Fix")
        parts.append(fix)
        parts.append("")

    # ── Code Snippet ──
    if project_root and file_path and line:
        snippet = _extract_snippet(project_root, file_path, line, snippet_lines)
        if snippet:
            parts.append("### Relevant Code")
            parts.append("```python")
            parts.append(snippet)
            parts.append("```")
            parts.append("")

    return "\n".join(parts)


def format_all_findings(
    findings: list[dict],
    scanner_name: str,
    project_root: str | None = None,
    errors: list[str] | None = None,
) -> str:
    """Format all findings from a scanner as a single AI context document.

    Args:
        findings: List of finding dicts from scan output.
        scanner_name: Name of the scanner.
        project_root: Absolute path to project root.
        errors: List of scanner error messages.

    Returns:
        Complete formatted document with all findings.
    """
    parts = []
    parts.append(f"# {scanner_name.title()} Scanner — AI Context Packet")
    parts.append(f"_Generated from scan results. {len(findings)} findings._")
    parts.append("")

    if errors:
        parts.append("## Scanner Errors")
        parts.append("These files could not be analyzed:")
        for err in errors:
            parts.append(f"- {err}")
        parts.append("")
        parts.append("---")
        parts.append("")

    for i, finding in enumerate(findings, 1):
        parts.append("---")
        parts.append(f"### Finding {i}/{len(findings)}")
        parts.append("")
        parts.append(format_finding_context(finding, scanner_name, project_root))

    return "\n".join(parts)


def _extract_snippet(
    project_root: str, file_path: str, line: int, context: int = 5
) -> str | None:
    """Extract a code snippet from the source file around the given line.

    Returns None if the file can't be read.
    """
    try:
        full_path = Path(project_root) / file_path
        if not full_path.exists():
            return None

        lines = full_path.read_text(encoding="utf-8").splitlines()
        start = max(0, line - context - 1)
        end = min(len(lines), line + context)

        snippet_lines = []
        for i in range(start, end):
            prefix = ">>>" if i == line - 1 else "   "
            snippet_lines.append(f"{prefix} {i + 1:4d} | {lines[i]}")

        return "\n".join(snippet_lines)
    except Exception:
        return None
