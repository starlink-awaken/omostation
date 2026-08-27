"""Gap analysis — identify under-researched topics and missing source diversity."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Gap:
    """A gap identified in the knowledge base."""

    topic: str
    gap_type: str  # "source_diversity", "depth", "missing_perspective", "coverage"
    description: str
    severity: str = "MEDIUM"
    recommendation: str = ""


@dataclass
class GapReport:
    """Results of a gap analysis."""

    gaps: list[Gap] = field(default_factory=list)
    total_reports_scanned: int = 0
    source_distribution: dict[str, int] = field(default_factory=dict)
    topic_frequency: dict[str, int] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        if not self.gaps:
            return f"Scanned {self.total_reports_scanned} reports. No significant gaps found."
        by_type = Counter(g.gap_type for g in self.gaps)
        parts = [f"Found {len(self.gaps)} gaps"]
        for gt, count in by_type.most_common():
            parts.append(f"{count} {gt}")
        parts.append(f"across {self.total_reports_scanned} reports.")
        return " ".join(parts)


class GapAnalyzer:
    """Analyze research coverage and identify gaps.

    Checks:
    - Source diversity: Are we using diverse source types?
    - Topic coverage: Which topics are well-covered vs. neglected?
    - Depth: Are there surface-level analyses without deep follow-ups?
    - Language coverage: Chinese vs English sources?
    """

    def __init__(self, report_dir: str = "~/knowledge/reports") -> None:
        self.report_dir = Path(report_dir).expanduser()

    def scan(self) -> GapReport:
        """Scan all reports for gaps."""
        report = GapReport()
        report_files = sorted(self.report_dir.glob("*.md"))
        report.total_reports_scanned = len(report_files)

        if not report_files:
            return report

        # Collect source URLs and topic data
        all_sources: list[str] = []
        topic_words: Counter = Counter()

        for f in report_files:
            try:
                content = f.read_text()
            except Exception:  # noqa: S112  # defensive fallback
                continue

            # Extract sources
            sources = re.findall(r"https?://[^\s\)]+", content)
            all_sources.extend(sources)

            # Extract topics from title
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).lower()
                words = re.findall(r"[a-z一-鿿]{3,}", title)
                topic_words.update(words)

        # Analyze source diversity
        report.source_distribution = self._classify_sources(all_sources)
        source_gaps = self._check_source_diversity(report.source_distribution)
        report.gaps.extend(source_gaps)

        # Topic coverage analysis
        report.topic_frequency = dict(topic_words.most_common(30))
        topic_gaps = self._check_topic_coverage(report_files, report.topic_frequency)
        report.gaps.extend(topic_gaps)

        return report

    def _classify_sources(self, urls: list[str]) -> dict[str, int]:
        """Classify source URLs by domain type."""
        categories: dict[str, int] = Counter()
        for url in urls:
            if "arxiv.org" in url:
                categories["academic_paper"] += 1
            elif "wikipedia.org" in url:
                categories["encyclopedia"] += 1
            elif "medium.com" in url or "towardsai" in url or "dev.to" in url:
                categories["tech_blog"] += 1
            elif "github.com" in url:
                categories["code"] += 1
            elif "youtube.com" in url or "bilibili.com" in url:
                categories["video"] += 1
            elif "zhihu.com" in url or "csdn.net" in url or "juejin.cn" in url:
                categories["chinese_platform"] += 1
            elif "runoob.com" in url or "cloud.tencent" in url or "cnblogs.com" in url:
                categories["chinese_doc"] += 1
            elif "linkedin.com" in url:
                categories["social_media"] += 1
            elif ".gov" in url or ".edu" in url:
                categories["official"] += 1
            else:
                categories["web"] += 1
        return dict(categories)

    def _check_source_diversity(self, distribution: dict[str, int]) -> list[Gap]:
        """Check if source types are sufficiently diverse."""
        gaps = []
        total = sum(distribution.values())

        if total == 0:
            gaps.append(
                Gap(
                    topic="global",
                    gap_type="source_diversity",
                    description="No sources found at all.",
                    severity="HIGH",
                    recommendation="Run research to populate the knowledge base.",
                )
            )
            return gaps

        # Check for missing academic sources
        academic_ratio = distribution.get("academic_paper", 0) / total
        if academic_ratio < 0.05:
            gaps.append(
                Gap(
                    topic="global",
                    gap_type="source_diversity",
                    description=(
                        f"Low academic source ratio ({academic_ratio:.1%}). Only {distribution.get('academic_paper', 0)} academic papers."
                    ),
                    severity="MEDIUM",
                    recommendation=("Enable arXiv/Semantic Scholar backends for more academic sources."),
                )
            )

        # Check for missing Chinese sources (if we have Chinese topics)
        chinese_total = distribution.get("chinese_platform", 0) + distribution.get("chinese_doc", 0)
        if chinese_total == 0 and total > 10:
            gaps.append(
                Gap(
                    topic="global",
                    gap_type="source_diversity",
                    description="No Chinese-language sources detected despite having many sources.",
                    severity="LOW",
                    recommendation="Enable 秘塔AI搜索 backend and search in Chinese.",
                )
            )

        return gaps

    def _check_topic_coverage(self, report_files: list[Path], topic_freq: dict[str, int]) -> list[Gap]:
        """Check for surface-level vs deep coverage gaps."""
        gaps = []

        # Check for topics with only single reports (no follow-up)
        report_topics: Counter = Counter()
        for f in report_files:
            try:
                content = f.read_text()
            except Exception:  # noqa: S112  # defensive fallback
                continue
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).lower()
                words = set(re.findall(r"[a-z]{4,}", title))
                for w in words:
                    report_topics[w] += 1

        # Flag topics with only 1 report
        single_report_topics = [
            t
            for t, c in report_topics.items()
            if c == 1
            and t
            not in {
                "research",
                "report",
                "architecture",
                "evolution",
                "language",
                "model",
                "transformer",
                "python",
                "asyncio",
                "openai",
                "google",
            }
        ]
        if len(single_report_topics) > 3:
            gaps.append(
                Gap(
                    topic="multiple",
                    gap_type="depth",
                    description=(
                        f"{len(single_report_topics)} topics have only a single research report. Deeper follow-up research recommended."
                    ),
                    severity="LOW",
                    recommendation=(f"Consider re-researching: {', '.join(single_report_topics[:5])}"),
                )
            )

        # Check for very frequent topics indicating broad but shallow coverage
        if report_files and len(report_files) > 20:
            top_5_topics = sorted(topic_freq.items(), key=lambda x: -x[1])[:5]
            if top_5_topics:
                gaps.append(
                    Gap(
                        topic="trending",
                        gap_type="coverage",
                        description=(
                            f"Top 5 most-researched terms: {', '.join(f'{t}({c})' for t, c in top_5_topics)}. Check for diminishing returns."
                        ),
                        severity="LOW",
                        recommendation="Consider exploring adjacent topics not yet covered.",
                    )
                )

        return gaps


def get_improvement_suggestions(report_dir: str = "~/knowledge/reports") -> list[str]:
    """Quick suggestions for knowledge base improvement without running full scan."""
    analyzer = GapAnalyzer(report_dir)
    result = analyzer.scan()
    suggestions = []
    for g in result.gaps:
        suggestions.append(f"[{g.severity}] {g.gap_type}: {g.recommendation}")
    if not suggestions:
        suggestions.append("Knowledge base coverage looks healthy!")
    return suggestions
