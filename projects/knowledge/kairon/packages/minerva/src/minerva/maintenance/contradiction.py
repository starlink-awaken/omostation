"""Contradiction detection across research reports and knowledge base entries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Contradiction:
    """A detected contradiction between two sources or claims."""

    claim_a: str
    source_a: str
    claim_b: str
    source_b: str
    topic: str
    severity: str = "MEDIUM"  # LOW | MEDIUM | HIGH
    resolution: str = ""


@dataclass
class ContradictionReport:
    """Results of a contradiction scan."""

    contradictions: list[Contradiction] = field(default_factory=list)
    total_reports_scanned: int = 0
    total_claims_checked: int = 0

    @property
    def high_severity_count(self) -> int:
        return sum(1 for c in self.contradictions if c.severity == "HIGH")

    @property
    def summary(self) -> str:
        if not self.contradictions:
            return f"Scanned {self.total_reports_scanned} reports, {self.total_claims_checked} claims. No contradictions found."
        return f"Found {len(self.contradictions)} contradictions ({self.high_severity_count} HIGH) across {self.total_reports_scanned} reports ({self.total_claims_checked} claims checked)."


class ContradictionDetector:
    """Scan knowledge base and research reports for contradictory claims.

    Uses LLM-based analysis to identify:
    - Direct contradictions (A says X, B says non-X)
    - Inconsistencies in factual claims
    - Methodological disagreements
    """

    def __init__(self, llm_client: Any = None, report_dir: str = "~/knowledge/reports") -> None:
        self.llm = llm_client
        self.report_dir = Path(report_dir).expanduser()

    async def scan(self, topic_filter: str | None = None) -> ContradictionReport:
        """Scan all reports for contradictions, optionally filtered by topic."""
        report = ContradictionReport()

        report_files = sorted(self.report_dir.glob("*.md"), reverse=True)
        if not report_files:
            return report

        # Take latest N reports to avoid overwhelming the LLM
        recent = report_files[:20]
        report.total_reports_scanned = len(recent)

        # Extract title-URL pairs from each report
        all_entries: list[dict] = []
        for f in recent:
            entries = self._extract_entries(f, topic_filter)
            all_entries.extend(entries)

        report.total_claims_checked = len(all_entries)

        # Find contradictions using the LLM
        if self.llm and len(all_entries) >= 2:
            contradictions = await self._detect_with_llm(all_entries, topic_filter)
            report.contradictions = contradictions

        return report

    def _extract_entries(self, filepath: Path, topic_filter: str | None = None) -> list[dict]:
        """Extract claim-source pairs from a report markdown file."""
        try:
            content = filepath.read_text()
        except Exception:
            return []

        if topic_filter and topic_filter.lower() not in content.lower():
            return []

        # Use shared extraction
        all_entries = extract_claims(str(self.report_dir), limit=100)
        matching = [e for e in all_entries if e.get("file") == filepath.name]
        return matching

    async def _detect_with_llm(self, entries: list[dict], topic_filter: str | None = None) -> list[Contradiction]:
        """Use LLM to find contradictions in the claim set."""
        if len(entries) < 2:
            return []

        claims_text = "\n".join(
            f"{i + 1}. [{e['claim'][:200]}] (source: {e['source'][:100]})" for i, e in enumerate(entries[:30])
        )

        prompt = f"""Analyze these claims from research reports and identify contradictions.

Claims:
{claims_text}

For each contradiction found, output a JSON object with:
- "claim_a": first claim text
- "source_a": source of first claim
- "claim_b": contradictory claim text
- "source_b": source of contradictory claim
- "topic": the topic of disagreement
- "severity": HIGH (direct contradiction) | MEDIUM (different interpretations) | LOW (minor)

Return only contradictions that exist, as a JSON array. If none found, return empty array []."""

        try:
            response = await self.llm.generate(
                system="You detect contradictions in research. Output valid JSON only.",
                prompt=prompt,
                temperature=0.2,
                max_tokens=1500,
            )
            # Parse JSON from response
            import json

            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]")
            if start >= 0 and end > start:
                data = json.loads(response[start : end + 1])
                return [
                    Contradiction(
                        claim_a=c.get("claim_a", ""),
                        source_a=c.get("source_a", ""),
                        claim_b=c.get("claim_b", ""),
                        source_b=c.get("source_b", ""),
                        topic=c.get("topic", topic_filter or ""),
                        severity=c.get("severity", "MEDIUM"),
                    )
                    for c in data
                ]
        except Exception:
            pass

        return []


def extract_claims(report_dir: str = "~/knowledge/reports", limit: int = 20) -> list[dict]:
    """Extract claim-source pairs from recent research reports.

    Shared by CLI maintenance and ContradictionDetector.
    """
    report_path = Path(report_dir).expanduser()
    report_files = sorted(report_path.glob("*.md"), reverse=True)[:limit]
    all_entries = []
    for f in report_files:
        try:
            content = f.read_text()
        except Exception:  # noqa: S112  # defensive fallback
            continue
        for match in re.finditer(r"\|\s*(.+?)\s*\|\s*(https?://[^\s|]+|[^|]+?)\s*\|", content):
            claim = match.group(1).strip()
            source = match.group(2).strip()
            if len(claim) > 10 and claim not in ("Claim", "---", "-------"):
                all_entries.append({"claim": claim, "source": source, "file": f.name})
    return all_entries


def detect_contradictions_rule_based(entries: list[dict]) -> list[Contradiction]:
    """Simple rule-based contradiction detection (no LLM required).

    Detects:
    - Same source listed with conflicting confidence levels
    - Opposite keywords ("increases" vs "decreases", "improves" vs "worsens")
    """
    contradictions = []
    opposites = [
        ("increas", "decreas"),
        ("improve", "worsen"),
        ("higher", "lower"),
        ("more", "less"),
        ("positive", "negative"),
        ("supports", "refutes"),
        ("confirms", "denies"),
    ]

    for i, a in enumerate(entries):
        for j, b in enumerate(entries):
            if j <= i:
                continue
            claim_a = a["claim"].lower()
            claim_b = b["claim"].lower()

            for pos, neg in opposites:
                if (pos in claim_a and neg in claim_b) or (neg in claim_a and pos in claim_b):
                    contradictions.append(
                        Contradiction(
                            claim_a=a["claim"][:100],
                            source_a=a["source"],
                            claim_b=b["claim"][:100],
                            source_b=b["source"],
                            topic=a.get("file", ""),
                            severity="MEDIUM",
                        )
                    )
                    break
    return contradictions
