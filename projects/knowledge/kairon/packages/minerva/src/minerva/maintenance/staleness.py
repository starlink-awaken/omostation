"""Staleness and recency checking for knowledge base entries and research reports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class StaleEntry:
    """A knowledge entry flagged as potentially outdated."""

    path: str
    title: str
    last_updated: str
    age_days: int
    reason: str
    source_count: int = 0
    newest_source_date: str = ""


@dataclass
class StalenessReport:
    """Results of a staleness scan."""

    stale_entries: list[StaleEntry] = field(default_factory=list)
    total_reports_scanned: int = 0
    total_stale: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for e in self.stale_entries if e.age_days > 180)

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.stale_entries if 90 < e.age_days <= 180)

    @property
    def summary(self) -> str:
        if not self.stale_entries:
            return f"Scanned {self.total_reports_scanned} reports. All up to date."
        return f"Found {self.total_stale} stale entries ({self.critical_count} critical >180d, {self.warning_count} warning >90d) out of {self.total_reports_scanned} reports."


class StalenessChecker:
    """Check knowledge base for outdated content.

    Flags reports that:
    - Are older than a configurable threshold (default: 90 days)
    - Reference sources older than a threshold
    - Have never been updated/refreshed
    """

    def __init__(
        self,
        report_dir: str = "~/knowledge/reports",
        warn_days: int = 90,
        critical_days: int = 180,
    ) -> None:
        self.report_dir = Path(report_dir).expanduser()
        self.warn_days = warn_days
        self.critical_days = critical_days

    def scan(self) -> StalenessReport:
        """Scan all reports for staleness."""
        report = StalenessReport()
        report_files = sorted(self.report_dir.glob("*.md"), key=lambda f: f.stat().st_mtime)
        report.total_reports_scanned = len(report_files)

        now = datetime.now()

        for f in report_files:
            try:
                entry = self._check_file(f, now)
                if entry:
                    report.stale_entries.append(entry)
            except Exception:
                pass

        report.total_stale = len(report.stale_entries)
        return report

    def _check_file(self, filepath: Path, now: datetime) -> StaleEntry | None:
        """Check a single report for staleness."""
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        age_days = (now - mtime).days

        if age_days < self.warn_days:
            return None  # Still fresh

        # Read the file to extract metadata
        try:
            content = filepath.read_text()
        except Exception:
            return None

        # Extract title from first H1
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else filepath.stem

        # Count sources
        sources = re.findall(r"https?://[^\s\)]+", content)
        source_count = len(sources)

        # Find newest source date
        dates = re.findall(r"(\d{4})[-/](\d{2})[-/](\d{2})", content)
        newest_date = ""
        for y, m, d in dates:
            try:
                dt = f"{y}-{m}-{d}"
                if dt > newest_date:
                    newest_date = dt
            except Exception:
                pass

        # Determine reason
        reason = (
            f"Critical: {age_days}d old (threshold: {self.critical_days}d)"
            if age_days > self.critical_days
            else f"Warning: {age_days}d old (threshold: {self.warn_days}d)"
        )

        if newest_date and (now - datetime.strptime(newest_date, "%Y-%m-%d")).days > self.critical_days:
            reason += f". All sources predate {newest_date}."

        return StaleEntry(
            path=str(filepath),
            title=title,
            last_updated=mtime.strftime("%Y-%m-%d"),
            age_days=age_days,
            reason=reason,
            source_count=source_count,
            newest_source_date=newest_date,
        )

    def get_topics_needing_refresh(self) -> list[str]:
        """Get list of topics that should be re-researched due to staleness."""
        report = self.scan()
        return [f"{e.title} ({e.age_days}d old, {e.source_count} sources)" for e in report.stale_entries[:10]]
