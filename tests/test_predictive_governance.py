"""测试 PredictiveGovernance"""

from pathlib import Path
from tempfile import TemporaryDirectory

from omo.predictive_governance import PredictiveGovernanceEngine


def test_engine_init():
    with TemporaryDirectory() as tmpdir:
        omo_dir = Path(tmpdir)
        (omo_dir / "_truth" / "registry").mkdir(parents=True, exist_ok=True)
        (omo_dir / "_truth" / "registry" / "debt.yaml").write_text("debts: []\n")

        engine = PredictiveGovernanceEngine(omo_dir)
        assert engine.debt_registry is not None


def test_forecast():
    with TemporaryDirectory() as tmpdir:
        omo_dir = Path(tmpdir)
        (omo_dir / "_truth" / "registry").mkdir(parents=True, exist_ok=True)
        (omo_dir / "_truth" / "registry" / "debt.yaml").write_text("debts: []\n")

        engine = PredictiveGovernanceEngine(omo_dir)
        forecast = engine.forecast_governance_risks()
        assert forecast.overall_risk_level in ["high", "medium", "low"]


def test_recommendations():
    with TemporaryDirectory() as tmpdir:
        omo_dir = Path(tmpdir)
        (omo_dir / "_truth" / "registry").mkdir(parents=True, exist_ok=True)
        (omo_dir / "_truth" / "registry" / "debt.yaml").write_text("debts: []\n")

        engine = PredictiveGovernanceEngine(omo_dir)
        actions = engine.recommend_proactive_actions()
        assert len(actions) > 0
