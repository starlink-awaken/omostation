"""Basic import verification for SSOT kernel.

Ensures all major modules can be imported and key symbols are accessible.
"""


def test_core_imports():
    from sot_bridge.ssot_kernel import config_loader, engine, meta_model, reporter, sync

    assert hasattr(meta_model, "MetaType")
    assert hasattr(meta_model, "Entity")
    assert hasattr(meta_model, "DomainConfig")
    assert hasattr(config_loader, "ConfigLoader")
    assert hasattr(config_loader, "load_domain")
    assert hasattr(engine, "RuleEngine")
    assert hasattr(engine, "CheckerRegistry")
    assert hasattr(reporter, "Reporter")
    assert hasattr(sync, "sync_yaml_to_markdown")


def test_patterns_import():
    from sot_bridge.ssot_kernel.patterns import base

    assert hasattr(base, "CheckResult")
    assert hasattr(base, "DerivationReport")
    assert hasattr(base, "BasePattern")
    assert hasattr(base, "DependencyValidator")


def test_extractor_import():
    from sot_bridge.ssot_kernel.extractor import ExtractionPipeline, TextSource

    assert TextSource is not None
    assert ExtractionPipeline is not None


def test_evolution_import():
    from sot_bridge.ssot_kernel.evolution import checkpoint, evolver, rule_miner

    assert hasattr(evolver, "Evolver")
    assert hasattr(checkpoint, "CheckpointManager")
    assert hasattr(rule_miner, "RuleMiner")
