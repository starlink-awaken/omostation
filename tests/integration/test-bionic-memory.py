#!/usr/bin/env python3
# ruff: noqa: D100,D103
"""test-bionic-memory.py -- 仿生记忆巩固集成测试 (BET-Y1Q4-T6-29)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bin.ops.bionic_memory_consolidation import (
    CausalTriple,
    NightlyDistillationEngine,
    SEMAExtractor,
    WorkingMemoryEvent,
)


class TestCausalTriple(unittest.TestCase):
    def test_valid_triple(self) -> None:
        triple = CausalTriple("X", "CAUSED", "Y", confidence=0.9)
        self.assertTrue(triple.is_valid(threshold=0.6))

    def test_invalid_low_confidence(self) -> None:
        triple = CausalTriple("X", "CAUSED", "Y", confidence=0.3)
        self.assertFalse(triple.is_valid(threshold=0.6))

    def test_boundary_confidence(self) -> None:
        triple = CausalTriple("X", "CAUSED", "Y", confidence=0.6)
        self.assertTrue(triple.is_valid(threshold=0.6))

    def test_serialization(self) -> None:
        triple = CausalTriple("A", "LEADS_TO", "B", confidence=0.8, source="test")
        d = triple.to_dict()
        self.assertEqual(d["subject"], "A")
        self.assertGreaterEqual(d["confidence"], 0.6)


class TestSEMAExtractor(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = SEMAExtractor()

    def test_causal_chain_pairing(self) -> None:
        """因为 X 所以 Y -> (X, CAUSED, Y) 配对优先."""
        event = WorkingMemoryEvent("lesson", "因为并发争用所以必须隔离", confidence=0.9)
        triples = self.extractor.extract_triples(event)
        self.assertGreater(len(triples), 0)
        self.assertEqual(triples[0].predicate, "CAUSED")
        self.assertEqual(triples[0].subject, "并发争用")
        self.assertEqual(triples[0].object, "必须隔离")

    def test_avoid_pattern(self) -> None:
        event = WorkingMemoryEvent("pitfall", "不要在生产环境直接 reset --hard", confidence=0.85)
        triples = self.extractor.extract_triples(event)
        avoid_triples = [t for t in triples if t.predicate == "AVOID"]
        self.assertGreater(len(avoid_triples), 0)

    def test_recommend_pattern(self) -> None:
        event = WorkingMemoryEvent("best_practice", "应该用 git tag 钉住交付", confidence=0.8)
        triples = self.extractor.extract_triples(event)
        rec_triples = [t for t in triples if t.predicate == "RECOMMEND"]
        self.assertGreater(len(rec_triples), 0)

    def test_metadata_driven(self) -> None:
        event = WorkingMemoryEvent("structured", "", confidence=0.75,
            metadata={"causal_subject": "practice", "causal_predicate": "RECOMMEND", "causal_object": "use worktree"})
        triples = self.extractor.extract_triples(event)
        self.assertGreater(len(triples), 0)


class TestNightlyDistillationEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = NightlyDistillationEngine(confidence_threshold=0.6)

    def test_dry_run_produces_stats(self) -> None:
        result = self.engine.run_consolidation(dry_run=True)
        self.assertIn("events_processed", result)
        self.assertTrue(result["dry_run"])

    def test_circuit_breaker_filters_low_confidence(self) -> None:
        result = self.engine.run_consolidation(dry_run=True)
        self.assertGreater(result["triples_rejected"], 0)

    def test_accepted_le_extracted(self) -> None:
        result = self.engine.run_consolidation(dry_run=True)
        self.assertLessEqual(result["triples_accepted"], result["triples_extracted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
