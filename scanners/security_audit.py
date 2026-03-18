"""Security Audit Scanner — auth decorator coverage checker.

Verifies that all routes have appropriate authentication decorators,
using the intentionally_public_routes allowlist for known exceptions.
"""

import time

from scanners.base import ScanFinding, ScanOutput


class SecurityAuditScanner:
    """Check routes for missing auth decorators."""

    name = "security"
    description = "Auth decorator coverage checker"
    version = "1.0"

    def scan(self, project_config, route_registry=None) -> ScanOutput:
        """Run the security audit.

        Args:
            project_config: ProjectConfig dataclass or dict.
            route_registry: Pre-built route registry from coupling scanner.
                           If None, runs the coupling scanner first.

        Returns:
            ScanOutput with findings about unprotected routes.
        """
        start = time.time()
        findings = []
        errors = []

        # Get route registry
        if route_registry is None:
            try:
                from scanners.coupling_audit import CouplingAuditScanner

                coupling = CouplingAuditScanner()
                coupling_result = coupling.scan(project_config)
                route_registry = coupling_result.route_registry
                errors.extend(coupling_result.errors)
            except Exception as e:
                errors.append(f"Failed to build route registry: {e}")
                elapsed = int((time.time() - start) * 1000)
                return ScanOutput(
                    findings=findings,
                    scanned_files=0,
                    errors=errors,
                    duration_ms=elapsed,
                )

        # Get config
        if hasattr(project_config, "conventions"):
            conventions = project_config.conventions
        else:
            conventions = project_config.get("conventions", {})

        public_routes = set(conventions.get("intentionally_public_routes", []))

        # Check each route
        for route in route_registry:
            route_id = self._route_id(route)
            has_auth = bool(route.get("auth_decorators"))

            if has_auth:
                continue

            # Check if intentionally public
            if route_id in public_routes:
                continue

            # No auth decorator — flag it
            methods = route.get("methods", ["GET"])
            is_mutating = any(m in methods for m in ["POST", "PUT", "DELETE", "PATCH"])

            if is_mutating:
                severity = "critical"
                msg = (
                    f"Unprotected mutating route: {route['url_pattern']} "
                    f"({', '.join(methods)}) has no auth decorator"
                )
            else:
                severity = "warning"
                msg = (
                    f"Unprotected route: {route['url_pattern']} "
                    f"({', '.join(methods)}) has no auth decorator"
                )

            findings.append(
                ScanFinding(
                    file=route.get("file", "unknown"),
                    line=route.get("line"),
                    message=msg,
                    severity=severity,
                    scanner=self.name,
                    details={
                        "function": route.get("function_name"),
                        "blueprint": route.get("blueprint"),
                        "url_pattern": route.get("url_pattern"),
                        "methods": methods,
                        "all_decorators": route.get("all_decorators", []),
                    },
                )
            )

        elapsed = int((time.time() - start) * 1000)
        return ScanOutput(
            findings=findings,
            scanned_files=len(route_registry),
            errors=errors,
            duration_ms=elapsed,
        )

    @staticmethod
    def _route_id(route: dict) -> str:
        """Build a blueprint.function route ID for allowlist matching."""
        bp = route.get("blueprint", "")
        fn = route.get("function_name", "")
        if bp:
            return f"{bp}.{fn}"
        return fn
