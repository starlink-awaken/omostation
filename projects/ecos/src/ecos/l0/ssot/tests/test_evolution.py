"""Tests for SSOT evolution module.

Covers: Evolver, RuleMiner, CheckpointManager, EvolutionReport.
"""

from pathlib import Path

from sot_bridge.ssot_kernel.engine import RuleEngine
from sot_bridge.ssot_kernel.evolution.checkpoint import CheckpointManager
from sot_bridge.ssot_kernel.evolution.evolver import Evolver
from sot_bridge.ssot_kernel.evolution.rule_miner import EvolutionReport, RuleMiner, RuleSuggestion
from sot_bridge.ssot_kernel.meta_model import (
    DomainConfig,
)


class TestEvolutionReport:
    def test_create(self):
        suggestions = [
            RuleSuggestion(
                id="SUG-001",
                pattern="contradiction",
                name="Suggestion 1",
                conditions=["A > B"],
                logic="if A > B then alert",
                confidence=0.9,
                tier="high",
                rationale="Detected pattern",
            ),
        ]
        report = EvolutionReport(
            suggestions=suggestions,
            checkpoint="cp-001",
            summary="Found 1 suggestion",
        )
        assert len(report.suggestions) == 1
        assert report.checkpoint == "cp-001"
        assert report.summary == "Found 1 suggestion"


class TestRuleSuggestion:
    def test_create(self):
        s = RuleSuggestion(
            id="SUG-002",
            pattern="chain_trigger",
            name="Test Suggestion",
            conditions=["X"],
            logic="X → Y",
            confidence=0.8,
            tier="medium",
            rationale="Observed pattern",
        )
        assert s.id == "SUG-002"
        assert s.confidence == 0.8
        assert s.tier == "medium"


class TestRuleMiner:
    def test_init(self):
        config = DomainConfig()
        report = RuleEngine().execute(config)
        miner = RuleMiner(config, report)
        assert miner.domain is config
        assert miner.report is report

    def test_mine_all_empty(self):
        config = DomainConfig()
        report = RuleEngine().execute(config)
        miner = RuleMiner(config, report)
        suggestions = miner.mine_all()
        assert isinstance(suggestions, list)


class TestCheckpointManager:
    def test_init(self, tmp_path: Path):
        cm = CheckpointManager(str(tmp_path))
        assert str(cm.domain_dir) == str(tmp_path)

    def test_create_checkpoint(self, tmp_path: Path):
        cm = CheckpointManager(str(tmp_path))
        name = cm.create("test-checkpoint")
        assert name is not None

    def test_list_checkpoints_empty(self, tmp_path: Path):
        cm = CheckpointManager(str(tmp_path))
        checkpoints = cm.list_checkpoints()
        assert isinstance(checkpoints, list)


class TestEvolver:
    def test_init(self, tmp_path: Path):
        """Evolver initializes but may fail on domain loading."""
        # Create minimal domain structure
        d = tmp_path / "test_evolve"
        d.mkdir()
        (d / "domain.yaml").write_text("domain:\n  name: evo-test")
        (d / "entities.yaml").write_text("entities: []")

        evolver = Evolver(str(d))
        assert evolver.domain_dir == str(d)

    def test_analyze_with_minimal_domain(self, tmp_path: Path):
        """Evolver.analyze() should handle a minimal domain gracefully."""
        d = tmp_path / "analyze_test"
        d.mkdir()
        (d / "domain.yaml").write_text("domain:\n  name: analyze-test")
        (d / "entities.yaml").write_text("entities: []")
        (d / "facts.yaml").write_text("policy: []\ndata: []")
        (d / "inferences.yaml").write_text("inferences: []")
        (d / "rules.yaml").write_text("rules: []")
        (d / "relations.yaml").write_text("relations: []")

        evolver = Evolver(str(d))
        # analyze() should succeed even with an empty domain
        report = evolver.analyze()
        assert hasattr(report, "suggestions")
        assert hasattr(report, "checkpoint")
        assert hasattr(report, "summary")
