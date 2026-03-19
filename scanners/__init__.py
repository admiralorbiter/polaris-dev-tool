"""Scanner registry — maps scanner names to classes."""

from scanners.coupling_audit import CouplingAuditScanner
from scanners.security_audit import SecurityAuditScanner
from scanners.doc_freshness import DocFreshnessScanner
from scanners.base import SCANNER_REGISTRY

SCANNER_REGISTRY["coupling"] = CouplingAuditScanner
SCANNER_REGISTRY["security"] = SecurityAuditScanner
SCANNER_REGISTRY["doc_freshness"] = DocFreshnessScanner
