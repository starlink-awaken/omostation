from __future__ import annotations

from pathlib import Path

from omo.omo_metrics_plot import write_metrics_trend


def test_metrics_plot_helper_writes_output(tmp_path: Path) -> None:
    path = write_metrics_trend(tmp_path, "demo trend\n")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "demo trend\n"
