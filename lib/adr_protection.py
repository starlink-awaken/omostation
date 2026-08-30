"""ADR creation protection mechanism — prevent duplicate ADR creation.

Provides:
- Duplicate detection by title similarity (Levenshtein + exact match)
- Atomic ADR number allocation with flock protection
- INDEX consistency verification
- Pre-creation validation

Designed to wrap existing swarm_discipline D1 infrastructure with
higher-level protection checks.

Usage:
    from lib.adr_protection import ADRProtection
    prot = ADRProtection(workspace_root)
    result = prot.validate_before_creation("My New ADR Title", number=440)
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Data classes ─────────────────────────────────────────────────────


@dataclass
class DuplicateMatch:
    """A potential duplicate ADR."""

    number: int
    filename: str
    title: str
    similarity: float  # 0.0-1.0
    match_type: str  # "exact_title", "similar_title", "same_number"


@dataclass
class ProtectionResult:
    """Result of a protection check."""

    ok: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicates: list[DuplicateMatch] = field(default_factory=list)
    allocated_number: int | None = None
    index_consistent: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": self.violations,
            "warnings": self.warnings,
            "duplicates": [
                {
                    "number": d.number,
                    "filename": d.filename,
                    "title": d.title,
                    "similarity": d.similarity,
                    "match_type": d.match_type,
                }
                for d in self.duplicates
            ],
            "allocated_number": self.allocated_number,
            "index_consistent": self.index_consistent,
            "details": self.details,
        }


# ── Title similarity ─────────────────────────────────────────────────


def _normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip ADR-NNNN prefix, dashes→spaces, collapse whitespace."""
    t = title.strip().lower()
    t = re.sub(r"^adr-\d{4}[:\s]*", "", t)
    t = re.sub(r"^\d{4}[-\s]*", "", t)
    t = re.sub(r"[-_]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute Levenshtein similarity ratio (0.0-1.0). Pure Python, no deps."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    len1, len2 = len(s1), len(s2)
    # Optimize: if lengths differ too much, early exit
    if abs(len1 - len2) > max(len1, len2) * 0.5:
        return 0.0
    # Use two-row DP for memory efficiency
    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)
    for i in range(1, len1 + 1):
        curr[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,  # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev, curr = curr, prev
    distance = prev[len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len) if max_len > 0 else 1.0


def _token_overlap_ratio(s1: str, s2: str) -> float:
    """Jaccard token overlap ratio."""
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)


def compute_title_similarity(title1: str, title2: str) -> float:
    """Combined similarity score: max of Levenshtein and token overlap."""
    n1 = _normalize_title(title1)
    n2 = _normalize_title(title2)
    if n1 == n2:
        return 1.0
    lev = _levenshtein_ratio(n1, n2)
    tok = _token_overlap_ratio(n1, n2)
    return max(lev, tok)


# ── ADR file parsing ─────────────────────────────────────────────────

ADR_FILENAME_RE = re.compile(r"^(\d{4})-(.+)\.md$")


def parse_adr_title(filepath: Path) -> str | None:
    """Extract title from ADR file: frontmatter title, then first H1, then filename."""
    content = None
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        content = None

    if content is not None:
        # Try frontmatter title first
        in_frontmatter = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "---":
                if in_frontmatter:
                    break  # end of frontmatter
                in_frontmatter = True
                continue
            if in_frontmatter:
                m = re.match(r"^title:\s*(.+)$", stripped, re.IGNORECASE)
                if m:
                    return m.group(1).strip().strip("\"'")

        # Fall back to first H1
        for line in content.splitlines():
            m = re.match(r"^#\s+(.+)$", line.strip())
            if m:
                return m.group(1).strip()

    # Fall back to filename (also used when file is unreadable/absent)
    fm = ADR_FILENAME_RE.match(filepath.name)
    if fm:
        return fm.group(2).replace("-", " ").title()
    return None


def list_adr_files(decisions_dir: Path) -> list[tuple[int, Path, str]]:
    """List all ADR files with (number, path, title)."""
    results: list[tuple[int, Path, str]] = []
    if not decisions_dir.is_dir():
        return results
    for f in sorted(decisions_dir.glob("*.md")):
        m = ADR_FILENAME_RE.match(f.name)
        if m:
            num = int(m.group(1))
            title = parse_adr_title(f) or m.group(2).replace("-", " ")
            results.append((num, f, title))
    return results


# ── INDEX consistency ────────────────────────────────────────────────

INDEX_FILENAME_RE = re.compile(r"(?<![a-zA-Z0-9_-])(\d{4}-[a-z0-9-]+\.md)\b")


def parse_index_references(index_path: Path) -> set[str]:
    """Parse INDEX.md and return set of referenced ADR filenames."""
    if not index_path.is_file():
        return set()
    try:
        content = index_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return set(INDEX_FILENAME_RE.findall(content))


def check_index_consistency(decisions_dir: Path) -> tuple[list[str], list[str]]:
    """Check INDEX consistency: (missing_from_index, stale_in_index).

    Returns:
        missing_from_index: ADR files on disk but not in INDEX
        stale_in_index: References in INDEX to non-existent files
    """
    index_path = decisions_dir / "INDEX.md"
    index_refs = parse_index_references(index_path)
    disk_files = {f.name for f in decisions_dir.glob("*.md") if ADR_FILENAME_RE.match(f.name)}

    missing_from_index = sorted(disk_files - index_refs)
    stale_in_index = sorted(index_refs - disk_files)
    return missing_from_index, stale_in_index


# ── Main protection class ────────────────────────────────────────────


class ADRProtection:
    """ADR creation protection mechanism.

    Wraps existing swarm_discipline D1 infrastructure with higher-level
    duplicate detection and INDEX consistency checks.
    """

    # Similarity thresholds
    SIMILARITY_ERROR = 0.85  # Very likely duplicate
    SIMILARITY_WARNING = 0.65  # Possible duplicate

    def __init__(self, workspace_root: Path | str):
        self.root = Path(workspace_root).resolve()
        self.decisions_dir = self.root / ".omo" / "_knowledge" / "decisions"
        self.claims_dir = self.root / ".omo" / "_delivery" / "adr-claims"
        self.index_path = self.decisions_dir / "INDEX.md"

    def find_duplicates(
        self,
        title: str,
        *,
        number: int | None = None,
        threshold: float | None = None,
    ) -> list[DuplicateMatch]:
        """Find potential duplicate ADRs by title similarity and number."""
        if threshold is None:
            threshold = self.SIMILARITY_WARNING

        adrs = list_adr_files(self.decisions_dir)
        matches: list[DuplicateMatch] = []

        for num, path, existing_title in adrs:
            # Exact number match
            if number is not None and num == number:
                matches.append(
                    DuplicateMatch(
                        number=num,
                        filename=path.name,
                        title=existing_title,
                        similarity=1.0,
                        match_type="same_number",
                    )
                )
                continue

            # Title similarity
            sim = compute_title_similarity(title, existing_title)
            if sim >= threshold:
                match_type = "exact_title" if sim >= self.SIMILARITY_ERROR else "similar_title"
                matches.append(
                    DuplicateMatch(
                        number=num,
                        filename=path.name,
                        title=existing_title,
                        similarity=round(sim, 3),
                        match_type=match_type,
                    )
                )

        # Sort by similarity descending
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    def check_index_consistency(self) -> tuple[list[str], list[str]]:
        """Check INDEX.md consistency with disk."""
        return check_index_consistency(self.decisions_dir)

    def validate_before_creation(
        self,
        title: str,
        *,
        number: int | None = None,
        session: str = "",
    ) -> ProtectionResult:
        """Full pre-creation validation.

        Checks:
        1. Duplicate detection by title similarity
        2. Number conflict with existing ADRs
        3. Number conflict with active claims
        4. INDEX consistency
        """
        result = ProtectionResult(ok=True)

        # 1. Duplicate detection
        duplicates = self.find_duplicates(title, number=number)
        for dup in duplicates:
            if dup.match_type == "same_number":
                result.ok = False
                result.violations.append(f"ADR-{dup.number:04d} already exists: {dup.filename}")
            elif dup.match_type == "exact_title":
                result.ok = False
                result.violations.append(
                    f"Exact title match with ADR-{dup.number:04d}: {dup.title} (similarity={dup.similarity:.1%})"
                )
            elif dup.similarity >= self.SIMILARITY_WARNING:
                result.warnings.append(
                    f"Similar title to ADR-{dup.number:04d}: {dup.title} (similarity={dup.similarity:.1%})"
                )
        result.duplicates = duplicates

        # 2. Check active claims
        if number is not None:
            try:
                sys.path.insert(0, str(self.root / "bin" / "gac"))
                from swarm_discipline import load_adr_claims

                claims = load_adr_claims(self.claims_dir)
                claim = claims.get(number)
                if claim and claim.get("session") != session:
                    result.ok = False
                    result.violations.append(f"ADR-{number:04d} already claimed by session={claim.get('session')}")
            except ImportError:
                result.warnings.append("Could not load swarm_discipline for claim check")

        # 3. INDEX consistency
        missing, stale = self.check_index_consistency()
        result.index_consistent = len(missing) == 0 and len(stale) == 0
        if missing:
            result.warnings.append(
                f"{len(missing)} ADR(s) on disk but missing from INDEX.md: "
                + ", ".join(missing[:5])
                + ("..." if len(missing) > 5 else "")
            )
        if stale:
            result.warnings.append(
                f"{len(stale)} stale reference(s) in INDEX.md: "
                + ", ".join(stale[:5])
                + ("..." if len(stale) > 5 else "")
            )

        result.details = {
            "total_adrs_on_disk": len(list_adr_files(self.decisions_dir)),
            "index_missing_count": len(missing),
            "index_stale_count": len(stale),
        }
        return result

    def allocate_number(
        self,
        session: str,
        *,
        preferred_number: int | None = None,
    ) -> tuple[bool, int | None, str]:
        """Atomically allocate an ADR number using swarm_discipline D1.

        Returns: (success, allocated_number, message)
        """
        try:
            sys.path.insert(0, str(self.root / "bin" / "gac"))
            from swarm_discipline import acquire_adr_claim

            ok, result = acquire_adr_claim(self.root, session, number=preferred_number)
            if ok:
                return True, result["number"], f"ADR-{result['next_id']} allocated"
            return False, None, result.get("error", "allocation failed")
        except Exception as e:
            return False, None, f"Allocation error: {e}"

    def verify_allocation(self, number: int, session: str) -> bool:
        """Verify that an ADR number is properly allocated to a session."""
        try:
            sys.path.insert(0, str(self.root / "bin" / "gac"))
            from swarm_discipline import load_adr_claims

            claims = load_adr_claims(self.claims_dir)
            claim = claims.get(number)
            return claim is not None and claim.get("session") == session
        except Exception:
            return False

    def get_protection_status(self) -> dict[str, Any]:
        """Get overall ADR protection status for reporting."""
        adrs = list_adr_files(self.decisions_dir)
        missing, stale = self.check_index_consistency()

        # Check for existing duplicates on disk
        from collections import Counter

        numbers = [n for n, _, _ in adrs]
        dup_numbers = [n for n, c in Counter(numbers).items() if c > 1]

        try:
            sys.path.insert(0, str(self.root / "bin" / "gac"))
            from swarm_discipline import load_adr_claims

            claims = load_adr_claims(self.claims_dir)
            active_claims = len(claims)
        except Exception:
            active_claims = -1

        return {
            "total_adrs": len(adrs),
            "duplicate_numbers": dup_numbers,
            "index_missing": missing,
            "index_stale": stale,
            "index_consistent": len(missing) == 0 and len(stale) == 0,
            "active_claims": active_claims,
            "protection_active": True,
        }
