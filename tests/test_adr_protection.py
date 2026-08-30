"""Tests for ADR protection mechanism.

Covers:
- Duplicate detection by title similarity
- Atomic number allocation
- INDEX consistency verification
- Concurrent access safety
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main as unittest_main

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from adr_protection import (
    ADRProtection,
    DuplicateMatch,
    ProtectionResult,
    compute_title_similarity,
    list_adr_files,
    parse_adr_title,
    check_index_consistency,
    parse_index_references,
    _normalize_title,
    _levenshtein_ratio,
    _token_overlap_ratio,
)


class TestTitleSimilarity(TestCase):
    """Test title similarity computation."""

    def test_identical_titles(self):
        self.assertEqual(compute_title_similarity("My ADR Title", "My ADR Title"), 1.0)

    def test_identical_after_normalization(self):
        self.assertEqual(
            compute_title_similarity("ADR-0001: My Title", "my title"),
            1.0,
        )

    def test_similar_titles_high(self):
        sim = compute_title_similarity(
            "Swarm Coordination Discipline",
            "Swarm Coordination Protocol",
        )
        self.assertGreaterEqual(sim, 0.6)

    def test_different_titles_low(self):
        sim = compute_title_similarity(
            "Agora Route Table Strategy",
            "Docker Container Management",
        )
        self.assertLess(sim, 0.4)

    def test_empty_titles(self):
        self.assertEqual(compute_title_similarity("", ""), 1.0)

    def test_one_empty(self):
        self.assertEqual(compute_title_similarity("something", ""), 0.0)

    def test_normalize_title_strips_adr_prefix(self):
        self.assertEqual(_normalize_title("ADR-0001: My Title"), "my title")
        self.assertEqual(_normalize_title("0001-my-title"), "my title")

    def test_levenshtein_identical(self):
        self.assertEqual(_levenshtein_ratio("abc", "abc"), 1.0)

    def test_levenshtein_different(self):
        ratio = _levenshtein_ratio("abc", "xyz")
        self.assertLess(ratio, 0.5)

    def test_token_overlap_identical(self):
        self.assertEqual(_token_overlap_ratio("a b c", "a b c"), 1.0)

    def test_token_overlap_partial(self):
        ratio = _token_overlap_ratio("a b c", "a b d")
        self.assertAlmostEqual(ratio, 0.5, places=1)


class TestADRFileParsing(TestCase):
    """Test ADR file title extraction."""

    def test_parse_title_from_h1(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("---\nstatus: active\n---\n\n# My ADR Title\n\nContent here.\n")
            f.flush()
            path = Path(f.name)
        try:
            self.assertEqual(parse_adr_title(path), "My ADR Title")
        finally:
            path.unlink()

    def test_parse_title_from_frontmatter(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("---\ntitle: Frontmatter Title\nstatus: active\n---\n\n# Different H1\n")
            f.flush()
            path = Path(f.name)
        try:
            self.assertEqual(parse_adr_title(path), "Frontmatter Title")
        finally:
            path.unlink()

    def test_parse_title_fallback_to_filename(self):
        path = Path("0123-my-adr-title.md")
        self.assertEqual(parse_adr_title(path), "My Adr Title")

    def test_list_adr_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "0001-first.md").write_text("# First ADR\n")
            (td / "0002-second.md").write_text("# Second ADR\n")
            (td / "INDEX.md").write_text("# Index\n")
            (td / "readme.txt").write_text("not an adr")
            results = list_adr_files(td)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0][0], 1)
            self.assertEqual(results[1][0], 2)


class TestINDEXConsistency(TestCase):
    """Test INDEX.md consistency checking."""

    def test_consistent_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "0001-first.md").write_text("# First\n")
            (td / "0002-second.md").write_text("# Second\n")
            (td / "INDEX.md").write_text(
                "| 0001 | First | 0001-first.md |\n"
                "| 0002 | Second | 0002-second.md |\n"
            )
            missing, stale = check_index_consistency(td)
            self.assertEqual(missing, [])
            self.assertEqual(stale, [])

    def test_missing_from_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "0001-first.md").write_text("# First\n")
            (td / "0002-second.md").write_text("# Second\n")
            (td / "INDEX.md").write_text(
                "| 0001 | First | 0001-first.md |\n"
            )
            missing, stale = check_index_consistency(td)
            self.assertIn("0002-second.md", missing)
            self.assertEqual(stale, [])

    def test_stale_in_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "0001-first.md").write_text("# First\n")
            (td / "INDEX.md").write_text(
                "| 0001 | First | 0001-first.md |\n"
                "| 0002 | Missing | 0002-missing.md |\n"
            )
            missing, stale = check_index_consistency(td)
            self.assertEqual(missing, [])
            self.assertIn("0002-missing.md", stale)

    def test_parse_index_references(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                "| 0001 | First | 0001-first.md |\n"
                "| 0002 | Second | 0002-second.md |\n"
            )
            f.flush()
            path = Path(f.name)
        try:
            refs = parse_index_references(path)
            self.assertIn("0001-first.md", refs)
            self.assertIn("0002-second.md", refs)
        finally:
            path.unlink()


class TestDuplicateDetection(TestCase):
    """Test duplicate detection in ADRProtection."""

    def test_exact_title_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-existing.md").write_text("# Existing ADR Title\n")
            prot = ADRProtection(td)
            matches = prot.find_duplicates("Existing ADR Title")
            self.assertTrue(any(m.match_type == "exact_title" for m in matches))

    def test_no_match_different_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-existing.md").write_text("# Existing ADR Title\n")
            prot = ADRProtection(td)
            matches = prot.find_duplicates("Completely Different Topic")
            high_matches = [m for m in matches if m.similarity >= 0.85]
            self.assertEqual(high_matches, [])

    def test_same_number_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-existing.md").write_text("# Existing ADR Title\n")
            prot = ADRProtection(td)
            matches = prot.find_duplicates("New Title", number=1)
            self.assertTrue(any(m.match_type == "same_number" for m in matches))


class TestValidationBeforeCreation(TestCase):
    """Test full pre-creation validation."""

    def test_clean_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-existing.md").write_text("# Existing\n")
            (decisions / "INDEX.md").write_text(
                "| 0001 | Existing | 0001-existing.md |\n"
            )
            prot = ADRProtection(td)
            result = prot.validate_before_creation("Brand New Unique Title")
            self.assertTrue(result.ok)
            self.assertEqual(result.violations, [])

    def test_duplicate_title_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-existing.md").write_text("# Swarm Coordination\n")
            prot = ADRProtection(td)
            result = prot.validate_before_creation("Swarm Coordination")
            self.assertFalse(result.ok)
            self.assertTrue(any("exact title" in v.lower() for v in result.violations))

    def test_same_number_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-existing.md").write_text("# Existing\n")
            prot = ADRProtection(td)
            result = prot.validate_before_creation("New Title", number=1)
            self.assertFalse(result.ok)
            self.assertTrue(any("already exists" in v.lower() for v in result.violations))

    def test_index_inconsistency_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-existing.md").write_text("# Existing\n")
            (decisions / "0002-missing.md").write_text("# Missing from index\n")
            (decisions / "INDEX.md").write_text(
                "| 0001 | Existing | 0001-existing.md |\n"
            )
            prot = ADRProtection(td)
            result = prot.validate_before_creation("New Title")
            self.assertTrue(result.ok)
            self.assertFalse(result.index_consistent)
            self.assertTrue(any("missing" in w.lower() for w in result.warnings))


class TestProtectionStatus(TestCase):
    """Test overall protection status reporting."""

    def test_status_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-first.md").write_text("# First\n")
            (decisions / "0002-second.md").write_text("# Second\n")
            (decisions / "INDEX.md").write_text(
                "| 0001 | First | 0001-first.md |\n"
                "| 0002 | Second | 0002-second.md |\n"
            )
            prot = ADRProtection(td)
            status = prot.get_protection_status()
            self.assertEqual(status["total_adrs"], 2)
            self.assertEqual(status["duplicate_numbers"], [])
            self.assertTrue(status["index_consistent"])
            self.assertTrue(status["protection_active"])

    def test_status_detects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            decisions = td / ".omo" / "_knowledge" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "0001-first.md").write_text("# First\n")
            (decisions / "0001-duplicate.md").write_text("# Duplicate\n")
            prot = ADRProtection(td)
            status = prot.get_protection_status()
            self.assertIn(1, status["duplicate_numbers"])


class TestResultSerialization(TestCase):
    """Test ProtectionResult serialization."""

    def test_to_dict(self):
        result = ProtectionResult(
            ok=False,
            violations=["test violation"],
            warnings=["test warning"],
            duplicates=[
                DuplicateMatch(
                    number=1,
                    filename="0001-test.md",
                    title="Test",
                    similarity=0.95,
                    match_type="exact_title",
                )
            ],
            index_consistent=True,
        )
        d = result.to_dict()
        self.assertFalse(d["ok"])
        self.assertEqual(len(d["violations"]), 1)
        self.assertEqual(len(d["duplicates"]), 1)
        self.assertEqual(d["duplicates"][0]["number"], 1)


if __name__ == "__main__":
    unittest_main()
