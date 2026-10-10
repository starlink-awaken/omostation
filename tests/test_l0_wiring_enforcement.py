"""L0 审计收口 — 强制力红测 (2026-10-10, audit F2/F3).

对每条『审计后仍声称被强制执行』的规则, 用合成违规证明它能红 (非零退出)。
不能红的规则不算被强制执行; 若有一天某条不再能红, 本文件对应的测试会当场
拦住它 (手工复核 + 修订即可)。

覆盖:
  - CR-OMO-DIRECT-IO-01: contract_gatekeeper 对 .omo/ 直写合成违规 exit 1
  - CR-KOS-CONSENSUS-RAG-01: _gate_injection 阈值门禁 (RAG=false / savings<50% 红)
  - CR-OMNIBUS-01: OmniEnvelope 拒绝非法 plane (bus-foundation 单测亦覆盖)
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATEKEEPER = ROOT / "projects/ecos/scripts/contract_gatekeeper.py"
OMO_LINT = ROOT / "projects/omo/src/omo/omo_lint.py"
KOS_INJECTOR = ROOT / "bin/gac/gac-consensus-inject.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# ── CR-OMO-DIRECT-IO-01: 合成 .omo 直写必须 exit 1 ──


def test_contract_gatekeeper_red_on_synthetic_direct_omo_io(tmp_path):
    """gatekeeper 对 .omo/ 直写合成违规必须报错 (audit F2: 可红才是强制执行)."""
    violation = tmp_path / "direct_omo_violation.py"
    violation.write_text(
        textwrap.dedent(
            """\
            from pathlib import Path
            Path(".omo/state/synth.yaml").write_text("boom", encoding="utf-8")
            """
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(GATEKEEPER), str(violation)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0, f"gatekeeper 必须红, got rc={r.returncode}: {r.stdout}"
    assert "forbidden direct mutation" in r.stdout or "violations detected" in r.stdout

    # 同文件去掉违规 → 绿 (证明是违规本身触发红, 不是装置恒红)
    clean = tmp_path / "clean_direct_omo.py"
    clean.write_text("x = 1\n", encoding="utf-8")
    r2 = subprocess.run(
        [sys.executable, str(GATEKEEPER), str(clean)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, f"无违规文件必须绿, got rc={r2.returncode}: {r2.stdout}"


def test_omo_lint_direct_omo_io_is_wired_to_gatekeeper():
    """cmd_lint_direct_omo_io 的真实执行链必须是 contract_gatekeeper (F2 引用校正).

    不做 import (omo 包依赖较重), 只做源码级断言: omo_lint.py 必须引用
    contract_gatekeeper 与 direct-io-baseline.yaml, 即非编译器恒绿分支.
    """
    src = OMO_LINT.read_text(encoding="utf-8")
    assert "contract_gatekeeper" in src
    assert "direct-io-baseline.yaml" in src
    assert re.search(r"def cmd_lint_direct_omo_io", src)


# ── CR-KOS-CONSENSUS-RAG-01: 阈值门禁合成违规 ──


def test_kos_gate_red_when_rag_disabled_or_savings_below_threshold(tmp_path):
    """_gate_injection: RAG=false / savings<50% → 红; savings>=50% → 绿."""
    mod = _load("kos_injector", KOS_INJECTOR)
    ok, reason = mod._gate_injection(rag_mode=False, injected=3, total=3)
    assert not ok, "全量注入必须被拒"
    assert "RAG" in reason
    ok, reason = mod._gate_injection(rag_mode=True, injected=2, total=3)
    assert not ok, "33% 节省必须被拒 (低于 50% 阈值)"
    assert "50%" in reason
    ok, _ = mod._gate_injection(rag_mode=True, injected=2, total=4)
    assert ok, "50% 边界必须放行"
    ok, _ = mod._gate_injection(rag_mode=True, injected=1, total=5)
    assert ok, "80% 节省必须放行"


def test_kos_injector_gate_before_write(tmp_path, monkeypatch):
    """main() 在 RAG 不可用时拒绝写入 CLAUDE.md (合成环境: 3 条基因, 无任务上下文)."""
    mod = _load("kos_injector_main", KOS_INJECTOR)
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "db_path", tmp_path / "kos-index.sqlite")
    monkeypatch.setattr(mod, "claude_md_path", tmp_path / "CLAUDE.md")
    # 无任务上下文 (tmp 不是 git 仓库) → rag_mode=False 全量 → 门禁红且不写盘
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE\n", encoding="utf-8")
    monkeypatch.setattr(
        mod, "_select_consensus_entities",
        lambda conn, full: [
            {"entity_id": "c1", "label": "L1", "source_file": str(tmp_path / "a.md")},
            {"entity_id": "c2", "label": "L2", "source_file": str(tmp_path / "b.md")},
            {"entity_id": "c3", "label": "L3", "source_file": str(tmp_path / "c.md")},
        ],
    )
    # 绕过真实 sqlite 连接
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "kos-index.sqlite"))
    conn.close()
    monkeypatch.setattr(mod, "sqlite3", sqlite3)
    # main() 里会先尝试 git/子进程读取任务上下文, tmp 非 git 仓库 → 异常吞掉 → task_context=""
    rc = mod.main()
    assert rc == 1, "无任务上下文 (RAG 不可用) 必须 exit 1"
    after = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert after == "# CLAUDE\n", "门禁拒绝时必须不落盘写入 ✅ -> CLAUDE.md 未变"


# ── CR-OMNIBUS-01: plane 合取红测 (bus-foundation 直接单测) ──


def test_omnibus_plane_rejects_bogus():
    """OmniEnvelope 拒绝非法 plane — 引用 bus-foundation 单测 (F3(i))."""
    import importlib.util as _ilu

    bf_env = ROOT / "projects/bus-foundation/src"
    if not (bf_env / "bus_foundation/envelope.py").is_file():
        import pytest

        pytest.skip("bus-foundation submodule not initialized")
    sys.path.insert(0, str(bf_env))
    from bus_foundation.envelope import OmniEnvelope

    try:
        OmniEnvelope(topic="x", source="bos://t", plane="BOGUS")
    except ValueError:
        return  # plane="BOGUS" 被拒 = 可红 ✓
    raise AssertionError("plane='BOGUS' 必须被拒绝 (CR-OMNIBUS-01 plane 合取)")


# ── P1/P3 (2026-10-10): 拆除三个 always-green 桩, 换真谓词 + 真数据 ──
# 每个桩必须: (a) 合成违规 → ok=False; (b) 真仓库 → ok=True (可红才是强制, 见 audit F2)。


def _load_l0_checker():
    spec = importlib.util.spec_from_file_location("l0_checker", ROOT / "bin/gac/check-l0-constraints.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["l0_checker"] = m
    spec.loader.exec_module(m)
    return m


def test_omo_surface_registration_red_on_unregistered_asset(tmp_path, monkeypatch):
    """P1: CR-OMO-SURFACE-01 —— 注册表缺一个真实 .omo 顶层资产 → red."""
    m = _load_l0_checker()
    surf = tmp_path / "surfaces.yaml"
    surf.write_text(
        "assets:\n  - id: OMO-TRUTH\n    ref: .omo/_truth/\n  - id: OMO-CONTROL\n    ref: .omo/_control/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "OMO_SURFACES", surf)
    ok, msg = m.check_omo_surface_registration()
    assert not ok, f"未登记资产必须 FAIL: {msg}"


def test_omo_surface_02_red_without_kernel_plane(tmp_path, monkeypatch):
    """P1: CR-OMO-SURFACE-02 —— 无 kernel_plane 条目 → red."""
    m = _load_l0_checker()
    surf = tmp_path / "surfaces2.yaml"
    surf.write_text(
        "governance_stack:\n  - id: state_plane\n    ref: .omo/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "OMO_SURFACES", surf)
    ok, msg = m.check_omo_surface_02()
    assert not ok, f"缺 kernel_plane 必须 FAIL: {msg}"


def test_x3_c01_red_on_missing_value_tier(tmp_path, monkeypatch):
    """P1: X3-C01 —— 域缺 value_tier 声明 → red (不再 advisory)."""
    m = _load_l0_checker()
    vs = tmp_path / "x3.yaml"
    vs.write_text(
        "domains:\n  OMO:\n    value_tier: 1\n    cost_attribution: implemented\n  Vault:\n    cost_attribution: planned\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "VALUE_STACK", vs)
    ok, msg = m.check_x3_c01()
    assert not ok, f"缺 value_tier 必须 FAIL: {msg}"


def test_x3_c02_red_on_tier1_no_cost_attribution(tmp_path, monkeypatch):
    """P3: X3-C02 —— tier-1 域 cost_attribution=none → red (真谓词, 非 X3-C01)."""
    m = _load_l0_checker()
    vs = tmp_path / "x3.yaml"
    vs.write_text(
        "domains:\n  OMO:\n    value_tier: 1\n    cost_attribution: none\n  CARDS:\n    value_tier: 2\n    cost_attribution: planned\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "VALUE_STACK", vs)
    ok, msg = m.check_x3_c02()
    assert not ok, f"tier-1 cost_attribution=none 必须 FAIL: {msg}"


def test_x3_c02_green_when_tier1_has_attribution():
    """P3: X3-C02 真仓库 (ecos governance/x3-value-stack.yaml) 必须绿."""
    m = _load_l0_checker()
    ok, msg = m.check_x3_c02()
    assert ok, f"真仓库必须绿: {msg}"


def test_c2g_v3_01_red_on_done_task_without_writeback(tmp_path, monkeypatch):
    """P5: CR-C2G-V3-01 —— done+context_uri 任务无 ssot_written_back → red.

    旧注记『无 ssot write-back 实现』错: 写侧存在, 缺的是读侧/调度; 本检查就是读侧."""
    m = _load_l0_checker()
    done = tmp_path / "done"
    done.mkdir(parents=True)
    (done / "TASK-X.yaml").write_text(
        "id: TASK-X\nstatus: done\ncontext_uri: bos://governance/tasks/planned/TASK-X\n",
        encoding="utf-8",
    )
    (done / "TASK-Y.yaml").write_text(
        "id: TASK-Y\nstatus: done\ncontext_uri: bos://governance/tasks/planned/TASK-Y\nssot_written_back: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "DONE_TASKS", done)
    ok, msg = m.check_c2g_v3_01()
    assert not ok, f"未回写任务必须 FAIL: {msg}"


def test_c2g_v3_01_hist_exemption_is_loud_not_silent(tmp_path, monkeypatch):
    """P5 consequence resolution (2026-10-10): 历史豁免必须显式 dated 注解且被报告,
    不允许静默跳过; 未注解的违规任务依旧 FAIL (门禁不被削弱)."""
    m = _load_l0_checker()
    done = tmp_path / "done"
    done.mkdir(parents=True)
    # 带合法历史注解的任务 -> 通过, 但出现在输出 (HIST 桶)
    (done / "HIST.yaml").write_text(
        "id: HIST\nstatus: done\ncontext_uri: bos://governance/tasks/planned/HIST\n"
        "ssot_writeback_hist:\n  annotated_at: '2026-10-01'\n  reason: predates enforcement\n",
        encoding="utf-8",
    )
    # 未注解违规任务 -> 仍 FAIL
    (done / "FRESH.yaml").write_text(
        "id: FRESH\nstatus: done\ncontext_uri: bos://governance/tasks/planned/FRESH\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "DONE_TASKS", done)
    ok, msg = m.check_c2g_v3_01()
    assert not ok, f"未注解违规任务必须仍 FAIL: {msg}"
    assert "FRESH" in msg, "违规任务必须出现在输出里"
    assert "HIST" in msg and "annotated" in msg, "历史豁免必须被显式报告, 不得静默"


def test_c2g_v3_01_hist_annotation_without_reason_still_fails(tmp_path, monkeypatch):
    """P5 consequence resolution: 只有 annotated_at 而无 reason 的注解不得豁免 (防 skip-list 滥用)."""
    m = _load_l0_checker()
    done = tmp_path / "done"
    done.mkdir(parents=True)
    (done / "BADHIST.yaml").write_text(
        "id: BADHIST\nstatus: done\ncontext_uri: bos://governance/tasks/planned/BADHIST\n"
        "ssot_writeback_hist:\n  annotated_at: '2026-10-01'\n  reason: ''\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(m, "DONE_TASKS", done)
    ok, msg = m.check_c2g_v3_01()
    assert not ok, f"无 reason 的历史注解不得豁免: {msg}"
    assert "BADHIST" in msg