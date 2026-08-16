"""
测试信息论层
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.theories.metrics import MetricsLayer


def test_compute_kqi(z_park_path):
    ml = MetricsLayer(z_park_path)
    kqi = ml.compute_kqi()
    assert kqi["kqi"] > 0
    assert kqi["n_facts"] >= 2
    assert kqi["entropy"] >= 0
    assert 0 <= kqi["coverage"] <= 1
    assert kqi["density"] >= 0


def test_entropy():
    ml = MetricsLayer(".")
    h = ml.entropy([0.5, 0.5])
    assert h > 0  # 两个等概率事件熵 > 0
    h2 = ml.entropy([0.99, 0.01])
    assert h2 < h  # 极端分布熵更低


def test_information_gain():
    ml = MetricsLayer(".")
    before = {"entropy": 10.0}
    after = {"entropy": 5.0}
    ig = ml.information_gain(before, after)
    assert ig == 5.0


def test_empty_project(tmp_path):
    (tmp_path / "facts").mkdir(parents=True)
    (tmp_path / "entities").mkdir()
    (tmp_path / "inferences").mkdir()
    (tmp_path / "scheme").mkdir()
    ml = MetricsLayer(tmp_path)
    kqi = ml.compute_kqi()
    assert kqi["kqi"] >= 0
    assert kqi["n_facts"] == 0
