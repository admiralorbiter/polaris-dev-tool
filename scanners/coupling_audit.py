"""Coupling Audit Scanner — route↔template sync checker.

Uses Python AST to analyze route files and detect:
- Orphaned templates (no route references them)
- Missing templates (route references a template that doesn't exist)
- Orphaned url_for targets (template references a route that doesn't exist)

Also builds the Route Registry as a side effect.
"""

import ast
import time
from pathlib import Path

from scanners.base import ScanFinding, ScanOutput


class CouplingAuditScanner:
    """Scan for route↔template coupling issues."""

    name = "coupling"
    description = "Route ↔ template sync checker"
    version = "1.0"

    def scan(self, project_config) -> ScanOutput:
        """Run the coupling audit.

        Args:
            project_config: ProjectConfig dataclass or dict with project settings.

        Returns:
            ScanOutput with findings. Also attaches `route_registry` to the output
            as an extra attribute for the route registry feature.
        """
        start = time.time()
        findings = []
        errors = []
        scanned = 0

        # Resolve paths
        if hasattr(project_config, "project_root"):
            root = Path(project_config.project_root)
            routes_dir = root / project_config.paths.get("routes", "routes/")
            templates_dir = root / project_config.paths.get("templates", "templates/")
            conventions = (
                project_config.conventions
                if hasattr(project_config, "conventions")
                else {}
            )
        else:
            root = Path(project_config["project_root"])
            routes_dir = root / project_config.get("paths", {}).get("routes", "routes/")
            templates_dir = root / project_config.get("paths", {}).get(
                "templates", "templates/"
            )
            conventions = project_config.get("conventions", {})

        auth_decorators = set(conventions.get("auth_decorators", []))
        render_fn = conventions.get("template_render_function", "render_template")

        # --- Phase 1: Discover all templates on disk ---
        templates_on_disk = set()
        if templates_dir.exists():
            for t in templates_dir.rglob("*.html"):
                rel = t.relative_to(templates_dir)
                templates_on_disk.add(str(rel).replace("\\", "/"))

        # --- Phase 2: Parse all route files ---
        route_registry = []
        templates_referenced = set()
        url_for_targets = set()

        if routes_dir.exists():
            for py_file in sorted(routes_dir.rglob("*.py")):
                scanned += 1
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                    rel_path = str(py_file.relative_to(root)).replace("\\", "/")

                    routes, templates, url_fors = self._analyze_module(
                        tree, rel_path, auth_decorators, render_fn
                    )
                    route_registry.extend(routes)
                    templates_referenced.update(templates)
                    url_for_targets.update(url_fors)

                except SyntaxError as e:
                    errors.append(f"{py_file}: SyntaxError: {e}")
                except UnicodeDecodeError as e:
                    errors.append(f"{py_file}: UnicodeDecodeError: {e}")
                except Exception as e:
                    errors.append(f"{py_file}: {type(e).__name__}: {e}")

        # --- Phase 3: Cross-reference ---

        # Orphaned templates (on disk but never referenced)
        orphaned = templates_on_disk - templates_referenced
        # Exclude partials and base templates from orphan detection
        orphaned = {
            t
            for t in orphaned
            if not t.startswith("partials/")
            and not t.startswith("_")
            and t != "base.html"
            and t != "base-nonav.html"
        }

        for template in sorted(orphaned):
            findings.append(
                ScanFinding(
                    file=f"templates/{template}",
                    line=None,
                    message=f"Orphaned template: '{template}' is not referenced by any route",
                    severity="warning",
                    scanner=self.name,
                )
            )

        # Missing templates (referenced but not on disk)
        missing = templates_referenced - templates_on_disk
        for template in sorted(missing):
            findings.append(
                ScanFinding(
                    file="(unknown route)",
                    line=None,
                    message=f"Missing template: '{template}' is referenced but does not exist",
                    severity="critical",
                    scanner=self.name,
                )
            )

        elapsed = int((time.time() - start) * 1000)
        output = ScanOutput(
            findings=findings,
            scanned_files=scanned,
            errors=errors,
            duration_ms=elapsed,
        )
        # Attach route registry as extra data
        output.route_registry = route_registry
        return output

    def _analyze_module(
        self,
        tree: ast.Module,
        file_path: str,
        auth_decorators: set,
        render_fn: str,
    ) -> tuple[list[dict], set[str], set[str]]:
        """Analyze an AST module for routes, templates, and url_for calls.

        Returns:
            (route_entries, template_names, url_for_targets)
        """
        routes = []
        templates = set()
        url_fors = set()

        # Detect blueprint variable name (e.g., `district_bp = Blueprint(...)`)
        blueprint_var = self._find_blueprint_var(tree)

        for node in ast.walk(tree):
            # Extract render_template() calls anywhere
            if isinstance(node, ast.Call):
                fn_name = self._get_call_name(node)
                if fn_name == render_fn and node.args:
                    tpl = self._get_string_value(node.args[0])
                    if tpl:
                        templates.add(tpl)
                elif fn_name == "url_for" and node.args:
                    target = self._get_string_value(node.args[0])
                    if target:
                        url_fors.add(target)

        # Extract route-decorated functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                route_info = self._extract_route_info(
                    node, file_path, blueprint_var, auth_decorators, render_fn
                )
                if route_info:
                    routes.append(route_info)

        return routes, templates, url_fors

    def _find_blueprint_var(self, tree: ast.Module) -> str | None:
        """Find the Blueprint variable name (e.g., 'district_bp')."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(
                        node.value, ast.Call
                    ):
                        fn_name = self._get_call_name(node.value)
                        if fn_name == "Blueprint":
                            return target.id
        return None

    def _extract_route_info(
        self,
        func: ast.FunctionDef,
        file_path: str,
        blueprint_var: str | None,
        auth_decorators: set,
        render_fn: str,
    ) -> dict | None:
        """Extract route metadata from a decorated function."""
        route_pattern = None
        http_methods = ["GET"]
        decorators_found = []
        auth_found = []

        for dec in func.decorator_list:
            dec_info = self._parse_decorator(dec, blueprint_var)
            if dec_info:
                dec_name, dec_args = dec_info
                if dec_name == "route":
                    # Extract pattern and methods
                    if dec_args.get("pattern"):
                        route_pattern = dec_args["pattern"]
                    if dec_args.get("methods"):
                        http_methods = dec_args["methods"]
                    decorators_found.append("route")
                else:
                    decorators_found.append(dec_name)
                    if dec_name in auth_decorators:
                        auth_found.append(dec_name)

        if route_pattern is None:
            return None

        # Find templates rendered in this function
        rendered_templates = []
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                fn_name = self._get_call_name(node)
                if fn_name == render_fn and node.args:
                    tpl = self._get_string_value(node.args[0])
                    if tpl:
                        rendered_templates.append(tpl)

        # Infer blueprint name from blueprint_var
        blueprint_name = (
            blueprint_var.replace("_bp", "").replace("_blueprint", "")
            if blueprint_var
            else None
        )

        return {
            "blueprint": blueprint_name,
            "url_pattern": route_pattern,
            "methods": http_methods,
            "function_name": func.name,
            "auth_decorators": auth_found,
            "all_decorators": decorators_found,
            "templates": rendered_templates,
            "file": file_path,
            "line": func.lineno,
        }

    def _parse_decorator(
        self, dec: ast.expr, blueprint_var: str | None
    ) -> tuple[str, dict] | None:
        """Parse a decorator node into (name, args)."""
        # Simple decorator: @login_required
        if isinstance(dec, ast.Name):
            return (dec.id, {})

        # Attribute decorator: @something.method (ignore)
        if isinstance(dec, ast.Attribute) and not isinstance(dec, ast.Call):
            return (dec.attr, {})

        # Call decorator: @bp.route("/path", methods=["GET"])
        if isinstance(dec, ast.Call):
            fn = dec.func

            # @bp.route(...)
            if isinstance(fn, ast.Attribute):
                if blueprint_var and isinstance(fn.value, ast.Name):
                    if fn.value.id == blueprint_var and fn.attr == "route":
                        args = {}
                        if dec.args:
                            args["pattern"] = self._get_string_value(dec.args[0])
                        for kw in dec.keywords:
                            if kw.arg == "methods":
                                args["methods"] = self._get_list_values(kw.value)
                        return ("route", args)
                    else:
                        return (fn.attr, {})
                return (fn.attr, {})

            # @decorator_func(args)
            if isinstance(fn, ast.Name):
                return (fn.id, {})

        return None

    @staticmethod
    def _get_call_name(node: ast.Call) -> str | None:
        """Get the function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    @staticmethod
    def _get_string_value(node: ast.expr) -> str | None:
        """Extract a string literal from an AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        # Handle JoinedStr (f-strings) — return None as we can't resolve them
        if isinstance(node, ast.JoinedStr):
            return None
        return None

    @staticmethod
    def _get_list_values(node: ast.expr) -> list[str]:
        """Extract a list of string literals from an AST node."""
        if isinstance(node, ast.List):
            return [
                e.value
                for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
        return []
