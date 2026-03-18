"""Scanner registry — maps scanner names to classes."""

from scanners.coupling_audit import CouplingAuditScanner
from scanners.security_audit import SecurityAuditScanner
from scanners.base import SCANNER_REGISTRY

SCANNER_REGISTRY["coupling"] = CouplingAuditScanner
SCANNER_REGISTRY["security"] = SecurityAuditScanner
