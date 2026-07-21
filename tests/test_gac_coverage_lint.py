"""test_gac_coverage_lint — 声明即执行覆盖率 test (防回归).

验证核心逻辑:
- evidence 全新鲜 → alive exit 0
- executor evidence 过期 → 休眠 exit 1
- 无 governance-checks.yaml → 不崩 exit 1
"""
import importlib.util
import os
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "gac-coverage-lint.py"

REGISTRY_CONTENT = """---
status: active
---
gac:
  rules:
    - id: TEST-RULE-1
      executor: [omo_audit]
    - id: TEST-RULE-2
      executor: [evidence_smoke]
"""


def _load_module():
    """加载 gac-coverage-lint 脚本为 module."""
    spec = importlib.util.spec_from_file_location("gac_coverage_lint", SCRIPT)
    assert spec is not None and spec.loader is not None, f"无法加载 {SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_registry(tmp_path: Path) -> Path:
    """造 governance-checks.yaml (含 2 rule: omo_audit + evidence_smoke)."""
    reg = tmp_path / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(REGISTRY_CONTENT, encoding="utf-8")
    return reg


def _make_fresh_evidence(tmp_path: Path):
    """造新鲜的 3 类 evidence 文件 (mtime=now)."""
    gov_hist = tmp_path / ".omo" / "_knowledge" / "governance-history.jsonl"
    gov_hist.parent.mkdir(parents=True, exist_ok=True)
    gov_hist.write_text('{"kind": "audit"}\n', encoding="utf-8")
    es_dir = tmp_path / ".omo" / "_delivery" / "evidence-smoke"
    es_dir.mkdir(parents=True, exist_ok=True)
    (es_dir / "today.json").write_text("{}", encoding="utf-8")
    fc_log = tmp_path / "runtime" / "cron" / "operating-rhythm-daily.log"
    fc_log.parent.mkdir(parents=True, exist_ok=True)
    fc_log.write_text("run\n", encoding="utf-8")


def test_all_executors_alive(tmp_path, monkeypatch):
    """evidence 全新鲜 (mtime=now) → alive exit 0."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    _make_registry(tmp_path)
    _make_fresh_evidence(tmp_path)
    assert mod.main() == 0


def test_stale_executor_detected(tmp_path, monkeypatch):
    """omo_audit evidence 过期 (> 48h) → 休眠 exit 1."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    _make_registry(tmp_path)
    _make_fresh_evidence(tmp_path)
    # 把 governance-history.jsonl mtime 设为 50h 前
    gov_hist = tmp_path / ".omo" / "_knowledge" / "governance-history.jsonl"
    old = time.time() - (50 * 3600)
    os.utime(gov_hist, (old, old))
    assert mod.main() == 1


def test_missing_evidence_detected(tmp_path, monkeypatch):
    """evidence 文件缺失 → 休眠 exit 1."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    _make_registry(tmp_path)
    # 不造 evidence (全缺) → omo_audit/evidence_smoke 都休眠
    assert mod.main() == 1


def test_no_registry_no_crash(tmp_path, monkeypatch):
    """无 governance-checks.yaml → 不崩, exit 1 (报 missing)."""
    mod = _load_module()
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    # 不造 registry
    assert mod.main() == 1
