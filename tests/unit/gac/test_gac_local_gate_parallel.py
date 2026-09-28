"""E1 gate 并行化 — 黑名单完备性测试 (2026-09-28).

`bin/gac/gac-local-gate.py` 的 E1 改造把「无副作用 gate」放进线程池并行，
只有 `SERIAL_ONLY` 黑名单里的 gate 保持串行。方案唯一的敞口是
**写类 gate 漏登记** —— 漏一个，它就会与其它 gate 并发读写同一份
工作区 / `.omo/state` / 子模块指针 ⇒ 数据竞争（且多为偶发 flake，难归因）。

所以本文件把「哪个 gate 为什么必须串行」从注释变成**可执行契约**：

  ① 普查账 `CENSUS_*`：2026-09-27 对 87 个 gate 的逐项读写普查结论（B/C/独占三类），
     黑名单必须完整覆盖 —— 这是「完备性」的 ground truth。
  ② 全量分类账 `PARALLEL_REVIEWED`：**每个非黑名单 gate 都必须被判为「复审过、可并行」**。
     未来新增 gate 若没进任何一本账 ⇒ 本文件失败，强制回归「它凭什么可以并行」的判断，
     而不是静默继承默认并行。
  ③ 命令层防线：并行 gate 的命令行不得携带写请求类 flag。

每个断言都配**正控制**（样本非空 / 检测器对故意注入的坏输入确实会红），
防「把账改空即绿」的假绿。

运行时等价性（串/并 PASS/FAIL 集合相等、stdout 行序一致）由本文件的
`run_checks` 用例（index 归位）加人工 A/B 实测覆盖 —— 设计依据见
memory `reference_ci_latency_and_localization.md` §10.4 / §10.5 / §10.6。
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-local-gate.py"

# ── ① 普查账：2026-09-27 对 87 个 gate 的逐项读写普查（命令级读写判定）────────
# B 类：写工作区 / .omo/state / 子模块指针
CENSUS_WRITE_WORKSPACE = frozenset(
    {
        "gac-validate",  # 有规则级错误时追加写 .omo/_knowledge/rule-violations.jsonl
        "install-watch-agent",  # 写 launchd plist
        # 同一脚本 bin/agent-workflow.py 内含 os.replace + write_run（8 个子命令）
        "agent-workflow-lint",
        "agent-workflow-integrations",
        "agent-workflow-adapters",
        "agent-workflow-bootstrap",
        "agent-workflow-verify-plan",
        "agent-workflow-compliance",
        "agent-workflow-doctor",
        "agent-workflow-observe",
    }
)
# C 类：网络 / 远程（并行会引发 remote 争用）
CENSUS_NETWORK = frozenset(
    {
        "pitfall-gat006-check",  # 实跑 git fetch origin main
        "gac-compute-onboard-check",  # curl/urllib 探测本地算力服务
    }
)
# 独占本机资源：socket / sqlite
CENSUS_EXCLUSIVE = frozenset(
    {
        "bus-e2e-harness",  # 起本机 ZMQ loopback socket + 子进程
        "gac-consensus-inject-check",  # 可能 ALTER sqlite (kos DB)
    }
)
CENSUS_SERIAL = CENSUS_WRITE_WORKSPACE | CENSUS_NETWORK | CENSUS_EXCLUSIVE
CENSUS_TOTAL_GATES = 87

# ── ② 全量分类账：普查中的 A 类（纯读/verification）逐一复审为「可并行」─────────
# 维护约定：新增 gate 必须显式加入本账（或 SERIAL_ONLY），否则本文件失败。
PARALLEL_REVIEWED = frozenset(
    """
    script-registry-validate gac-drift write-owner-audit test-mcp-kos check-cockpit-ui-dist
    governance-evolution mof-schema-validate mof-state-bridge mof-drift m4-bootstrap-reflex
    m4-mcp-tool-integrity doc-ssot-lint project-layer-index doc-ssot-snapshots doc-link-check
    change-lane-check dependency-baseline-drift matrix-consistency governance-semantic-gate
    adr-coverage state-freshness-check p74-silent-workflows check-dashboard-registry-consistency
    check-toolbox-ssot check-domain-m1-alignment test-gac-engine service-config-validate
    service-config-drift zones-check omo-state-write-guard brief-protect
    mof-capabilities-drift-check doc-claims-check layer-call-direction-check
    check-severity-registry check-work-landed check-governance-ratio check-redline-coverage
    check-workorder-schema check-dual-track-purity check-silent-loss
    check-adversarial-effectiveness check-llm-gateway-only ci-surfaces-check
    bet-retro-due-check resident-status-check resident-mof-sync-check resident-bos-check
    sfop-slots execution-chain capability-ownership derived-only-fast-track auto-fix-loop
    command-discovery current-state-coherence check-submodule-rewind
    check-evidence-honest-closure check-gateway-status-doc check-foundry-deck-coverage
    check-evidence-freshness check-governance-trend bus-usage-report bos-tracking-gate
    check-index-drift root-directory-governance bin-scripts-convergence-audit
    omo-runtime-final-tree doc-governance check-conflict-markers check-swarm-collision
    bin-quota-diff task-field-governance test-collection
    """.split()
)

# ── ③ 命令层防线：请求「写」的 flag（gate 命令一旦带这些就不该进并行）────────
WRITE_REQUEST_FLAGS = frozenset(
    {"--write", "--fix", "--apply", "--stamp", "--bump", "--commit", "--no-dry-run", "--write-back"}
)


def _load_module():
    spec = importlib.util.spec_from_file_location("gac_local_gate_parallel", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _gate_ids(module) -> set[str]:
    return {gate["id"] for gate in module.GATES_LIST}


def _write_flags(command: list[str]) -> set[str]:
    """命令里显式请求写入的 flag（只看 flag token，不看脚本名/路径）。"""
    return {token for token in command[1:] if token in WRITE_REQUEST_FLAGS}


# ── ① 黑名单 ⊇ 普查账 ──────────────────────────────────────────────────


def test_blacklist_covers_every_census_serial_class() -> None:
    module = _load_module()

    missing = sorted(CENSUS_SERIAL - module.SERIAL_ONLY)
    assert not missing, (
        f"普查判定必须串行的 gate 未进 SERIAL_ONLY: {missing} —— "
        "漏登记 = 与其它 gate 并发读写同一份工作区/state/submodule ⇒ 数据竞争"
    )

    # 正控制：普查账三国类都非空（防「把账改空」使上面恒真）
    assert len(CENSUS_WRITE_WORKSPACE) == 10
    assert len(CENSUS_NETWORK) == 2
    assert len(CENSUS_EXCLUSIVE) == 2
    assert len(CENSUS_SERIAL) == 14


def test_blacklist_has_no_typos_or_ghost_entries() -> None:
    module = _load_module()
    gate_ids = _gate_ids(module)

    ghosts = sorted(module.SERIAL_ONLY - gate_ids)
    assert not ghosts, f"SERIAL_ONLY 含未登记/拼错的 gate（对它们并行化无效）: {ghosts}"

    # 与脚本内静态守卫共用同一判据：两处口径不得漂移
    assert module._unknown_serial_only == frozenset()

    # 正控制：同一个差集运算对幽灵 id 确实报出来（证明上面不是恒真）
    assert (set(module.SERIAL_ONLY) | {"no-such-gate"}) - gate_ids == {"no-such-gate"}


# ── ② 全量分类：新增 gate 不得静默继承「默认并行」─────────────────────────


def test_every_gate_is_explicitly_classified() -> None:
    module = _load_module()
    gate_ids = _gate_ids(module)
    classified = set(module.SERIAL_ONLY) | set(PARALLEL_REVIEWED)

    unclassified = sorted(gate_ids - classified)
    if unclassified:
        pytest.fail(
            f"新增 gate 未分类（不能默认并行）: {unclassified}\n"
            "请判断它是否写工作区/.omo/state/子模块指针、是否走网络、是否独占本机资源：\n"
            "  · 命中任一项 ⇒ 加入 bin/gac/gac-local-gate.py 的 SERIAL_ONLY + 本文件 CENSUS_*\n"
            "  · 确认无副作用 ⇒ 加入本文件 PARALLEL_REVIEWED"
        )

    stale = sorted(classified - gate_ids)
    assert not stale, f"分类账含已不存在的 gate（须同步删除）: {stale}"

    assert module.SERIAL_ONLY.isdisjoint(PARALLEL_REVIEWED)
    # 正控制：两本账并集非空且规模与普查一致（87 = 14 串行 + 73 并行）
    assert len(gate_ids) == CENSUS_TOTAL_GATES
    assert len(PARALLEL_REVIEWED) == CENSUS_TOTAL_GATES - len(CENSUS_SERIAL)


# ── ③ 命令层防线 ───────────────────────────────────────────────────────


def test_parallel_gate_commands_request_no_writes() -> None:
    module = _load_module()

    offenders = {
        gate["id"]: sorted(_write_flags([str(t) for t in gate["command"]]))
        for gate in module.GATES_LIST
        if gate["id"] not in module.SERIAL_ONLY and _write_flags([str(t) for t in gate["command"]])
    }
    assert not offenders, (
        f"并行 gate 的命令行请求了写入: {offenders} —— 要么它该进 SERIAL_ONLY，"
        "要么 flag 用错了（gate 命令应为只读语义）"
    )

    # 正控制：检测器对坏输入确实会红、对正常只读 flag 不误报
    assert _write_flags(["x.py", "--json"]) == set()
    assert _write_flags(["x.py", "--write"]) == {"--write"}


# ── ④ 一键回退 + index 归位（§10.4-4 / §10.4-2 的硬要求）──────────────────


def test_gate_jobs_env_override_and_default_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()

    monkeypatch.setenv("GAC_GATE_JOBS", "1")
    assert module._gate_jobs() == 1  # 完全回退串行，无需回滚代码

    monkeypatch.setenv("GAC_GATE_JOBS", "3")
    assert module._gate_jobs() == 3

    monkeypatch.setenv("GAC_GATE_JOBS", "not-a-number")
    assert 1 <= module._gate_jobs() <= 8

    monkeypatch.delenv("GAC_GATE_JOBS", raising=False)
    assert 1 <= module._gate_jobs() <= 8


def test_run_checks_preserves_order_and_serializes_blacklist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    checks = [
        ("agent-workflow-lint", ["fake"]),  # SERIAL_ONLY（写类）
        ("sfop-slots", ["fake"]),  # 可并行
        ("gac-validate", ["fake"]),  # SERIAL_ONLY（写类）
        ("execution-chain", ["fake"]),  # 可并行
    ]
    seen: list[tuple[str, str]] = []

    def fake_run_check(name: str, command: list[str]) -> dict[str, object]:
        seen.append((name, threading.current_thread().name))
        return {"name": name, "command": command, "ok": True}

    monkeypatch.setattr(module, "run_check", fake_run_check)
    main_thread = threading.main_thread().name

    monkeypatch.delenv("GAC_GATE_JOBS", raising=False)  # 默认并行
    results = module.run_checks(checks)
    expected_order = [name for name, _ in checks]
    assert [r["name"] for r in results] == expected_order  # index 归位 = 契约测试安全

    # 正控制：样本里确实各有串行/并行项，且并行项真的走了线程池
    serial_seen = {name for name, _ in seen if name in module.SERIAL_ONLY}
    parallel_seen = {name for name, _ in seen if name not in module.SERIAL_ONLY}
    assert serial_seen == {"agent-workflow-lint", "gac-validate"}
    assert parallel_seen == {"sfop-slots", "execution-chain"}
    assert all(thread == main_thread for name, thread in seen if name in serial_seen)
    assert any(thread != main_thread for name, thread in seen if name in parallel_seen)

    # GAC_GATE_JOBS=1 ⇒ 全部回主线程串行
    seen.clear()
    monkeypatch.setenv("GAC_GATE_JOBS", "1")
    results = module.run_checks(checks)
    assert [r["name"] for r in results] == expected_order
    assert all(thread == main_thread for _, thread in seen)
