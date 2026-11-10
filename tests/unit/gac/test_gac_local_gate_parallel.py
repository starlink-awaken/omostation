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
import subprocess
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
# 2026-10-31: 87 -> 88 (ADR-0122 §46 lane 欠账台账自洽 gate 加入, #4990)。
# 该 gate 的命令是 `lane-debt-ledger.py --check` —— 只读台账 YAML, 不写工作区 /
# .omo/state / 子模块指针, 不走网络, 不占独占本机资源 ⇒ 属 A 类, 可并行。
#
# 2026-10-31: 88 -> 94 (分类账改按**全集**核对)。
# gate 清单有两套来源 (submodule 内的 sgf-policy.yaml / 脚本内置 DEFAULT_POLICY
# fallback), 两者内容不同 ⇒ 两环境的清单分别是 88 / 84 个, 并集 94。
# 账只覆盖其中一套 ⇒ 换台机器 (子模块 init 与否) 判据结论就变 ⇒ 漏登记的
# 写类 gate 会在某台机器上静默继承「默认并行」。故普查口径改为全集。
# 2026-11-10: 95 -> 96 (CRON-BARE-PYTHON3-PY39-IMPORT-DEATH 决策(3) 的
# cron-interpreter-executability gate 加入 gac-local-gate.py GATES_LIST)。
# 该 gate 只读 .omo/cron/registry.yaml 并对候选解释器跑 find_spec 探测子进程，
# 不写工作区 / .omo/state / 子模块指针，不走网络，不占独占本机资源 ⇒ A 类，可并行。
# 2026-11-10: 96 -> 97 (PANORAMA-GATE-DETAIL-UNRELIABLE ③ 的
# gate-detail-contract 加入 GATES_LIST)。该 gate 只读 ~/.local/share/zhixing-dashboard/
# 的两份 JSON 平面，不写盘、不起子进程、不走网络、无独占资源 ⇒ A 类，可并行。
CENSUS_TOTAL_GATES = 97

# ── ② 全量分类账：普查中的 A 类（纯读/verification）逐一复审为「可并行」─────────
# 维护约定：新增 gate 必须显式加入本账（或 SERIAL_ONLY），否则本文件失败。
#
# 末尾 6 个（bdsk-shadow-sandbox / debt-integrity-check / error-knowledge-check /
# submodule-ancestry-gate / sweep-index-check / test-coverage-check）**只存在于
# DEFAULT_POLICY fallback** —— 子模块缺席时才会被加载，故必须一并登记（否则它们
# 在缺子模块的检出里未分类 ⇒ 静默继承「默认并行」）。逐个查过脚本体：均只读，
# 不写工作区/.omo/state/子模块指针，不走网络，不占独占本机资源 ⇒ A 类，可并行：
#   bdsk-shadow-sandbox     只跑 `git diff HEAD` 扫描文本
#   debt-integrity-check    只读债务登记 YAML + 查文件是否存在
#   error-knowledge-check   `error-knowledge.py check` 只校验坑库一致性
#   submodule-ancestry-gate `check-submodule-rewind.py --range ... --no-write-debt`
#                           （--no-write-debt 显式禁写；无 --range 的主路径本就不写盘）
#   sweep-index-check       `sweep_index.py --check` 只比对不落盘（写需 --write）
#   test-coverage-check     只扫项目目录有无测试
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
    check-index-drift scene-v3-guardrail root-directory-governance bin-scripts-convergence-audit
    omo-runtime-final-tree doc-governance check-conflict-markers check-swarm-collision
    bin-quota-diff task-field-governance test-collection
    lane-debt-ledger
    bdsk-shadow-sandbox debt-integrity-check error-knowledge-check
    submodule-ancestry-gate sweep-index-check test-coverage-check
    cron-interpreter-executability
    gate-detail-contract
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


# ── 门禁全集 (两套 policy 来源的并集) ───────────────────────────────────────
#
# `gac-local-gate.py` 的 gate 清单随「ecos 子模块是否在场」而变：
#   · 子模块在场  → 读 submodule 里的 `sgf-policy.yaml` (77 个 gate)
#   · 子模块缺席  → 退回脚本内置 `DEFAULT_POLICY` (72 个 gate)
# 两套来源**内容不同**（各有对方没有的 gate），实测两环境的清单分别是 88 / 84 个。
#
# 所以分类账必须覆盖的是**全集**（94 个），而不是「当前环境恰好加载的那一套」——
# 否则在缺子模块的检出里，那 6 个只存在于 fallback 的 gate 会因未登记而恒红，
# 而它们在有子模块的环境里同样会被执行 ⇒ 漏登记 = 写类 gate 静默继承「默认并行」。
#
# SGF policy 在子模块缺席时仍可从 **git 对象**读到（主仓用 gitlink 锁定了
# `projects/ecos` 的 commit），故全集在任何环境下都可算，无需依赖检出形态。


def _git_output(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else ""


def _sgf_policy_ids(module) -> tuple[set[str], bool]:
    """SGF policy（ecos 子模块内）声明的 gate id 集合 + 是否读到。

    优先读工作树里的文件；子模块缺席时从 **git 对象**读主仓 gitlink 锁定的那一版
    （`git ls-tree HEAD projects/ecos` → 该 commit 的 blob）。

    两者都拿不到（既无子模块工作树、又无子模块 git 对象）时返回 `(空集, False)`
    —— 此时**无法判定**「账里的 gate 是否已从 SGF policy 中消失」，故「陈旧项」
    方向不可判；只保留「每个可见 gate 都必须已分类」这一硬方向（见 `_gate_universe`）。
    """
    policy_path = Path(module.SGF_POLICY_YAML)
    if policy_path.is_file():
        import yaml

        data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        return {gate["id"] for gate in data.get("gates", [])}, True

    # 子模块不在场：从 git 对象读锁定版
    workspace = Path(module.WORKSPACE).resolve()
    try:
        rel = policy_path.resolve().relative_to(workspace)
    except ValueError:
        return set(), False
    parts = rel.parts
    if len(parts) < 3:
        return set(), False
    sub_path = "/".join(parts[:2])  # projects/ecos
    inner_path = "/".join(parts[2:])  # src/.../sgf-policy.yaml

    ls_tree = _git_output(["ls-tree", "HEAD", sub_path], workspace).split()
    if len(ls_tree) < 3:
        return set(), False
    pinned_sha = ls_tree[2]

    common = _git_output(["rev-parse", "--git-common-dir"], workspace).strip()
    if not common:
        return set(), False
    common_dir = Path(common)
    if not common_dir.is_absolute():
        common_dir = workspace / common_dir
    submodule_git_dir = common_dir.resolve() / "modules" / sub_path
    if not submodule_git_dir.is_dir():
        return set(), False

    blob = _git_output(
        [
            f"--git-dir={submodule_git_dir}",
            "cat-file",
            "blob",
            f"{pinned_sha}:{inner_path}",
        ],
        workspace,
    )
    if not blob:
        return set(), False
    import yaml

    data = yaml.safe_load(blob) or {}
    return {gate["id"] for gate in data.get("gates", [])}, True


def _gate_universe(module) -> tuple[set[str], bool]:
    """本仓在任何检出形态下可能出现的 gate id 全集 + 全集是否完整。

    = 当前环境加载的清单 ∪ DEFAULT fallback 清单 ∪ SGF policy 清单。

    三者取并集 ⇒ 与「子模块是否在场」无关，判据在任何检出形态下口径一致。

    第二个返回值表示全集是否**完整**（SGF policy 是否读到）：
      · 完整 ⇒ 「账里的 gate 是否已不存在」可判（陈旧项方向硬判）
      · 不完整 ⇒ 该方向不可判，跳过（但不放过「可见 gate 未分类」这一硬方向）
    """
    default_ids = {gate["id"] for gate in module.DEFAULT_POLICY["gates"]}
    sgf_ids, sgf_readable = _sgf_policy_ids(module)
    return _gate_ids(module) | default_ids | sgf_ids, sgf_readable


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
    # 用**全集**而非「当前环境加载的那一套」：清单随子模块是否在场而变
    # （88 / 84），按全集核对 ⇒ 判据在任何检出形态下口径一致。
    gate_ids, universe_complete = _gate_universe(module)
    classified = set(module.SERIAL_ONLY) | set(PARALLEL_REVIEWED)

    # 硬方向（任何环境下都判）：每个**可见** gate 都必须已分类。
    unclassified = sorted(gate_ids - classified)
    if unclassified:
        pytest.fail(
            f"新增 gate 未分类（不能默认并行）: {unclassified}\n"
            "请判断它是否写工作区/.omo/state/子模块指针、是否走网络、是否独占本机资源：\n"
            "  · 命中任一项 ⇒ 加入 bin/gac/gac-local-gate.py 的 SERIAL_ONLY + 本文件 CENSUS_*\n"
            "  · 确认无副作用 ⇒ 加入本文件 PARALLEL_REVIEWED"
        )

    # 陈旧方向（账里含已不存在的 gate）：需全集完整才能判 ——
    # SGF policy 读不到时，无法判定某 gate 是否已从 policy 中消失。
    if universe_complete:
        stale = sorted(classified - gate_ids)
        assert not stale, f"分类账含已不存在的 gate（须同步删除）: {stale}"

    assert module.SERIAL_ONLY.isdisjoint(PARALLEL_REVIEWED)
    # 正控制：两本账并集非空且规模与普查一致（全集 = 14 串行 + 80 并行）
    assert len(PARALLEL_REVIEWED) == CENSUS_TOTAL_GATES - len(CENSUS_SERIAL)


def test_census_size_matches_the_gate_universe() -> None:
    """普查总数必须等于门禁全集的规模。

    这是「账的规模」与「实际门禁数量」之间唯一的锚：
      · 全集变大（policy 新增 gate）⇒ 这里红 ⇒ 逼人登记
      · 全集变小（policy 删除 gate）⇒ 这里红 ⇒ 逼人从账里删
    两者方向都覆盖，故与 `test_every_gate_is_explicitly_classified` 的
    「陈旧项」判定互为冗余（覆盖 ⊆ 已分类 + 规模相等 ⇒ 两集合相等）。

    全集不完整时（SGF policy 读不到）无法比规模 ⇒ 跳过该方向。
    """
    module = _load_module()
    gate_ids, universe_complete = _gate_universe(module)
    if not universe_complete:
        pytest.skip("SGF policy 读不到（无子模块工作树且无子模块 git 对象）⇒ 全集不完整，规模不可比")
    assert len(gate_ids) == CENSUS_TOTAL_GATES, (
        f"普查总数 {CENSUS_TOTAL_GATES} 与门禁全集规模 {len(gate_ids)} 不符 —— "
        "gate 清单变了（policy 增删）⇒ 同步更新分类账与本常量"
    )


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
