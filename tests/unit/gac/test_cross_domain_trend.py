import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "cross-domain-trend.py"
REAL_OUTPUT = REPO_ROOT / ".omo" / "state" / "runtime" / "cross-domain-trend.json"
# 模块导入时取快照 —— 必须在**任何用例跑之前**, 否则同文件里靠前的用例会先污染,
# 守卫再比对就成了「自己跟自己的污染结果比」(2026-11-13 自测踩到)。
_REAL_OUTPUT_SNAPSHOT = REAL_OUTPUT.read_bytes() if REAL_OUTPUT.is_file() else None


def run_trend(
    args: list[str] | None = None,
    registry_content: str | None = None,
    registry_file: Path | None = None,
    output: Path | None = None,
) -> subprocess.CompletedProcess:
    """跑脚本，**始终**显式给 `--output`。

    2026-11-13: 原实现只传 `--registry`, 于是脚本落到自己的 DEFAULT_OUTPUT =
    **真实的** `.omo/state/runtime/cross-domain-trend.json` —— 本文件的 fixture
    数据（2026-01-01..05、values [1,1,0,0,0]）因此**一直在覆盖生产投影**,
    实测那份产物的 days 就是 fixture 的日期。不传 `--output` 就不再允许。
    """
    if output is None:
        fd, name = tempfile.mkstemp(prefix="cross-domain-trend-", suffix=".json")
        os.close(fd)
        output = Path(name)
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    if registry_file:
        cmd.extend(["--registry", str(registry_file)])
    cmd.extend(["--output", str(output)])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, input=registry_content)


class TestCrossDomainTrend:
    def test_analyze_governance_trend(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {
                "check": "check-a",
                "duration_ms": 10.0,
                "timestamp": f"2026-01-0{i}T00:00:00Z",
                "ok": True,
                "reason": "ok",
            }
            for i in range(1, 6)
        ]
        metrics_file.write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries),
            encoding="utf-8",
        )
        reg = tmp_path / "trend-fusion.yaml"
        reg.write_text(
            f"""version: 1
domains:
  governance:
    description: test
    source: {metrics_file}
    adapter: governance-trend-adapter
    enabled: true
    metrics: [gate_pass_rate]
fusion:
  weights:
    governance: 1.0
  alert_threshold: 0.3
""",
            encoding="utf-8",
        )
        result = run_trend(["--window", "5"], registry_file=reg)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["fusion"]["trend"] == "healthy"
        assert "governance" in data["domains"]

    def test_disabled_domain_skipped(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        metrics_file.write_text(
            json.dumps(
                {
                    "check": "check-a",
                    "duration_ms": 10.0,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "ok": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        reg = tmp_path / "trend-fusion.yaml"
        reg.write_text(
            f"""version: 1
domains:
  governance:
    description: test
    source: {metrics_file}
    enabled: false
    metrics: []
fusion:
  weights:
    governance: 1.0
""",
            encoding="utf-8",
        )
        result = run_trend(["--window", "5"], registry_file=reg)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["domains"] == {}

    def test_declining_trend_detected(self, tmp_path: Path):
        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [
            {
                "check": "check-a",
                "duration_ms": 10.0,
                "timestamp": f"2026-01-0{i}T00:00:00Z",
                "ok": i < 3,
                "reason": "fail",
            }
            for i in range(1, 6)
        ]
        metrics_file.write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries),
            encoding="utf-8",
        )
        reg = tmp_path / "trend-fusion.yaml"
        reg.write_text(
            f"""version: 1
domains:
  governance:
    description: test
    source: {metrics_file}
    adapter: governance-trend-adapter
    enabled: true
    metrics: [gate_pass_rate]
fusion:
  weights:
    governance: 1.0
  alert_threshold: 0.3
""",
            encoding="utf-8",
        )
        result = run_trend(["--window", "5"], registry_file=reg)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        gov = data["domains"].get("governance", {})
        assert gov.get("trend") == "declining"

    def test_run_trend_never_touches_the_real_projection(self, tmp_path: Path) -> None:
        """守卫：跑本文件的用例不得改动真实产物 `.omo/state/runtime/cross-domain-trend.json`。

        改前 `run_trend` 不传 `--output`, 三次调用都在往生产投影写 fixture 数据
        （实测那份产物的 `days` 就是 2026-01-01..05）。这条用例把「不被改动」
        钉住, 而不是只钉「新写法有传 --output」—— 后者会被下一次重构绕过。
        """
        before = _REAL_OUTPUT_SNAPSHOT

        metrics_file = tmp_path / "metrics-store.jsonl"
        entries = [{"timestamp": f"2026-01-0{i}T00:00:00Z", "check": f"c{i}", "ok": i <= 2}
                   for i in range(1, 6)]
        metrics_file.write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8"
        )
        reg = tmp_path / "trend-fusion.yaml"
        reg.write_text(
            f"""version: 1
domains:
  governance:
    description: test
    source: {metrics_file}
    adapter: governance-trend-adapter
    enabled: true
    metrics: [gate_pass_rate]
fusion:
  weights:
    governance: 1.0
  alert_threshold: 0.3
""",
            encoding="utf-8",
        )
        result = run_trend(["--window", "5"], registry_file=reg)
        assert result.returncode == 0

        after = REAL_OUTPUT.read_bytes() if REAL_OUTPUT.is_file() else None
        assert after == before, "跑测试改动了真实投影产物"
