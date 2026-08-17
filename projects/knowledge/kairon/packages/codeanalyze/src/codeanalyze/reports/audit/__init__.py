"""Knowledge audit — cross-validate raw documents against curated wiki.

Maintains backward compatibility by re-exporting all public symbols.
"""

from codeanalyze.reports.audit.models import AuditGroup, AuditReport  # type: ignore[import-not-found]
from codeanalyze.reports.audit.pipeline import run_audit  # type: ignore[import-not-found]

__all__ = ["AuditGroup", "AuditReport", "run_audit"]
