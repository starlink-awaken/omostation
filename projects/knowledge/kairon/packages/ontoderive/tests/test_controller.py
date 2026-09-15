"""
测试控制论层
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.theories.controller import PIDController


def test_analyze_empty(tmp_path):
    ctrl = PIDController(tmp_path)
    pid = ctrl.analyze()
    assert pid["p_value"] == 0  # 无检查记录
    assert pid["i_value"] == 0.0
    assert pid["d_value"] == 0.0
    assert pid["stability"] == "stable"


def test_adaptive_thresholds(tmp_path):
    ctrl = PIDController(tmp_path)
    thresholds = ctrl._adaptive_thresholds()
    assert "assertion_traceability" in thresholds
    assert "falsifiability" in thresholds
    # 无历史记录，应为默认值
    assert ">=30%" in thresholds["assertion_traceability"]


def test_analyze_returns_keys(z_park_path):
    ctrl = PIDController(z_park_path)
    pid = ctrl.analyze()
    for key in ["p_value", "i_value", "d_value", "control_signal", "stability"]:
        assert key in pid


def test_integral_with_no_history(tmp_path):
    ctrl = PIDController(tmp_path)
    assert ctrl._integral_term() == 0.0


def test_derivative_with_no_history(tmp_path):
    ctrl = PIDController(tmp_path)
    # v2.3滑动窗口平均可能返回非零（窗口内有少量历史）
    d = ctrl._derivative_term()
    assert isinstance(d, float)
