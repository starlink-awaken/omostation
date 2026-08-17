"""Tests for kairon_observability.anomaly — 滑窗异常检测 (Welford).

补 anomaly 零测试债 (功能 P1, 355 LOC 核心模块零覆盖)."""

from kairon_observability.anomaly import AnomalyDetector, AnomalyResult


def test_anomaly_result_defaults():
    r = AnomalyResult(is_anomaly=False, value=1.0)
    assert r.mean == 0.0
    assert r.stddev == 0.0
    assert r.z_score == 0.0
    assert r.threshold == 3.0
    assert r.trend == "stable"


def test_detector_update_returns_result():
    det = AnomalyDetector()
    r = det.update(1.0)
    assert isinstance(r, AnomalyResult)
    assert r.value == 1.0


def test_detector_warmup_no_anomaly():
    """预热期 + 正常值不该报异常."""

    det = AnomalyDetector(window_size=100, z_threshold=3.0)
    for v in [1.0, 1.1, 0.9, 1.0, 1.05, 0.95]:
        r = det.update(v)
        assert not r.is_anomaly


def test_detector_detects_spike():
    """稳定基线后突变该报异常."""
    det = AnomalyDetector(window_size=50, z_threshold=3.0)
    for _ in range(20):
        det.update(10.0)
    r = det.update(100.0)
    assert r.is_anomaly
    assert r.z_score > 3.0


def test_detector_get_stats_dict():
    det = AnomalyDetector()
    det.update(1.0)
    det.update(2.0)
    stats = det.get_stats()
    assert isinstance(stats, dict)


def test_detector_detect_spike_method_returns_bool():
    det = AnomalyDetector()
    result = det.detect_spike([1.0, 1.1, 1.0, 5.0])
    assert isinstance(result, bool)


def test_detector_detect_trend_returns_str():
    det = AnomalyDetector()
    trend = det.detect_trend([1.0, 2.0, 3.0, 4.0, 5.0])
    assert isinstance(trend, str)
    assert trend in ("increasing", "decreasing", "stable", "insufficient_data")


def test_detector_rolling_mean():
    det = AnomalyDetector()
    det.update(1.0)
    det.update(2.0)
    m = det.get_rolling_mean()
    assert isinstance(m, float)


def test_detector_window_size_caps_history():
    """window_size 该限制 history 长度."""
    det = AnomalyDetector(window_size=5)
    for v in range(10):
        det.update(float(v))
    assert len(det._history) == 5


def test_detector_adaptive_threshold_enable():
    det = AnomalyDetector()
    det.enable_adaptive_threshold(target_rate=0.05, step=0.1)
    # 不报错即可 (adaptive 状态设置)


def test_detector_rolling_percentile():
    det = AnomalyDetector()
    for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
        det.update(v)
    p50 = det.get_rolling_percentile(50.0)
    assert isinstance(p50, float)
