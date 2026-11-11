"""写面根钉死门禁：`bin/**` 里由 `__file__` 反推检出根再拼 profile 写面路径的站点，收成 shrink_only 基线。

契约: `docs/superpowers/specs/2026-10-13-writeplane-root-pin-gate.md`（判据即该文件 §3）
ADR:  `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`（读/写分根）
BET:  BET-Y2Q4-T10-250

三层判据，缺一层就会留下"门禁绿着但写面仍钉在检出"的缝：
- **自证**（AGENTS.md §7②）：注入两种命中形状（名字派生 / 内联派生），检测器必须点名 ——
  没有这条，"绿"可能只是检测器压根没命中。
- **反过宽**（§7④）：经缝取根、拼读面（`.omo/_truth` / `.omo/_knowledge`）都不得计入门禁集合，
  但读面两条必须由同一扫描分类出来（可见不计）。否则"往基线里塞几百条"也能凑过对拍。
- **双向相等**（§7⑤）：新增一处 ⇒ 红；改掉一处不缩基线 ⇒ 红。只断言 ⊆ 则还掉的债会悄悄消失。

本文件的 `ROOT` 由 `__file__` 反推是被检对象决定的：扫描的是"这份检出自己的源码"，
不是 profile 根。用 `code_root()` 反而会在声明 `OMOSTATION_ROOT` 时扫到别的树。
风险由 `test_scan_target_is_the_checkout_holding_this_test` 兜住（根不对就当场红，不空绿）。

2026-11-05 BET-Y2Q4-T10-288 起本文件有**第二把尺**：`scan_cwd_relative_sites` 认第四类根 ——
`Path(".omo")` 这类**不挂任何根**的相对锚，落点随**进程 CWD**，连 profile 都不读，所以第一把尺
（按 resolver 归类）与 `test_resident_write_plane_split` 的 state 族**按构造都看不见它**。
两把尺是并列类目而不是同一判据的放宽：第一把尺的 `SPEC_MARKER_READINGS` 五个**分桶**读数逐字不变，
否则一次改判据就会把债基线一起改写。契约见
`docs/superpowers/specs/2026-11-05-cwd-relative-root-anchor-admission.md` §2/§5 AC-01。

2026-11-06 BET-Y2Q4-T10-289 AC-02 改的是**门禁集合的准入谓词**（`gated_pairs`），不是分桶：
排除面由「按 marker 前缀」改为「按族」—— `.omo/_delivery` / `.omo/_knowledge` / `.omo/_truth` 是
读写混合面，整串排除会让「写者已迁 state 根、读者仍钉检出」的真缺陷与合法读面同形（spec §7 AC-02）。
族的名单**不在本文件复制**，由 `_state_families()` 从尺 A 的 `STATE_FAMILIES` 按 AST 取。
后果如实记账：门禁三读数 153/143/95 → 173/163/107，新入账的 20 处不是新债，是同一批站点先前
不计；`SPEC_MARKER_READINGS` 五桶逐字未变（分桶口径没动，动的只是「计不计」）。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / "bin"

# 整面都是写目标的两类（spec §1）：这两串前缀本身即 profile 面，按前缀判与按族判在此等价。
GATED_MARKERS = (".omo/state", "runtime")
# 其余四类是读写混合面 / 全机协调桥 / 署名文档面。混合面**不再整串排除**（AC-02），改由下面的
# `_family_of` 决定计不计；`kos` 没有任何登记族，因此实际仍不计 —— 那不是特例，是判据的输出。
ALL_MARKERS = (".omo/state", ".omo/_delivery", ".omo/_knowledge", ".omo/_truth", "runtime", "kos")
SKIP_SEGMENTS = {"_archive", "_vendored", "__pycache__", ".venv"}

RULER_A = ROOT / "tests" / "unit" / "test_resident_write_plane_split.py"


def _state_families() -> frozenset[str]:
    """state 族名单的**单一来源** = 尺 A 的 `STATE_FAMILIES`，只按 AST 取字面量，不 exec 那个文件。

    不复制一份名单的理由是 AGENTS.md §7「检测器的分类规则要与标记清单同源」与 T10-239「契约名单
    由源码判据导出且单一来源，消费者只 import」—— 两处各抄一份，就是下一个「漏认一半」的事故。
    用 AST 而不是 importlib：尺 A 的用例 `test_two_rulers_agree_on_the_relative_face` 会反过来
    载入本文件，exec 会造出双向加载；只读文本取常量则两边都在自己的树上求值，尺 A 改了这里立刻
    跟着变，不需要有人记得同步。
    **取不到就抛错，不退回空集**：退回空集是 §7⑧「坏了与内容为空同形」，会让按族门禁静默退回
    marker 前缀，读数看着正常（153/143/95）而判据已经不存在。
    """
    tree = ast.parse(RULER_A.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "STATE_FAMILIES" for t in node.targets
        ):
            return frozenset(
                c.value
                for c in ast.walk(node.value)
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            )
    raise AssertionError(f"{RULER_A} 里取不到 STATE_FAMILIES 赋值，按族判据已失效")


STATE_FAMILIES = _state_families()

# 能决定「计不计」的族必须有名有姓。摘掉两类：
# ① 通配项（`.omo/state/*`、`…/watermarks/*`）匹配一片而不是一个面，拿它判等于用前缀判；
# ② 容器 `.omo/_knowledge` 匹配它的**一切**后代，用它判就是把「整串排除」反着搬回来 —— 那样
#    44 个未登记的合法读面会全部入账，正是 AC-02 禁止的退化（spec §7 AC-02 末句）。
GATEABLE_FAMILIES = frozenset(
    f for f in STATE_FAMILIES if "*" not in f and f != ".omo/_knowledge"
)


def _family_of(whole: str) -> str | None:
    """整条拼接路径落到的**最具体**登记族；不落任何族 ⇒ None（由同一扫描分类出来，但不计）。"""
    hits = [f for f in GATEABLE_FAMILIES if whole == f or whole.startswith(f + "/")]
    return max(hits, key=len) if hits else None


# spec §1 的读数表 —— 与本文件扫描出的分类逐桶相等（同一判据、同一次扫描产出）。
# 2026-10-29 T10-278 读侧收敛把 resident-orchestrator 的 4 处检出根常量改成 state_root()
# 调用时刻解析，`.omo/_delivery` 桶按实测 82→78 重签（spec §1 表由 docs lane 同步）。
# 2026-11-02 T10-280 还掉 panorama-collect 的 event-ledger 站点（改挂 event_ledger_path()）：
# `runtime` 桶 51→50，门禁三读数 154/144/95 → 153/143/95（该文件另有 3 处仍钉检出根，故文件数不变）。
SPEC_MARKER_READINGS = {
    # 2026-10-31 ADR-0122 历史欠账处置: 新增 .omo/_truth/registry/lane-debt-ledger.yaml
    # => `.omo/_truth` 桶 161 -> 162 (该桶是排除面, 不影响门禁管辖的 154/144/95)。
    # 2026-11-05 DEBT-20260927-RUN-REGISTRY-RACE (PR #5059): auto-pruner 新增
    # `_run_update_lock()`，其取注册表的链 WORKSPACE_ROOT / ".omo" / "_truth" / ...
    # 是新的一处钉检出根站点 => `.omo/_truth` 162 -> 163。
    # 2026-11-11 BET-Y2Q4-T10-347: gac-bootstrap 新增层6, 其登记面常量
    # CI_SURFACES = WORKSPACE / ".omo" / "_truth" / "registry" / "ci-surfaces.yaml"
    # 是新的一处钉检出根站点 => `.omo/_truth` 163 -> 164。
    ".omo/_truth": 164,
    ".omo/state": 103,
    ".omo/_delivery": 78,
    "runtime": 50,
    ".omo/_knowledge": 62,
}
# 2026-11-06 BET-Y2Q4-T10-289 AC-02（准入谓词改按族，**分桶读数一条未动**）：门禁三读数
# 153/143/95 → 173/163/107。差额 20 站点 / 20 对 / 12 个文件里 9 个是新出现的文件，逐项是
# `.omo/_knowledge` 13 处 + `.omo/_delivery` 6 处 + `.omo/_truth` 1 处（spec §2 只裁了
# `_knowledge` 桶，另两个 marker 的 7 处是同一判据的连带命中，逐面裁决见 ADR-0456 addendum）。
SPEC_GATED_SITES = 173
SPEC_GATED_PAIRS = 163
SPEC_GATED_FILES = 107

# 2026-10-13 由 BET-Y2Q4-T10-250 的扫描生成的登记面（(文件, 拼出的相对路径) 去重）。
# 还掉一处债 = 从这份名单里删掉那一行，且必须同时改掉那个脚本；名单只减不增。
BASELINE_WRITESPANE_PAIRS = frozenset(
    [
        ('bin/bc-os/evolution-proposal-triage.py', '.omo/state/evolution-proposals-archived.json'),
        ('bin/bc-os/evolution-proposal-triage.py', '.omo/state/evolution-proposals.json'),
        ('bin/bc-os/evolution_engine.py', '.omo/state/evolution-proposals.json'),
        ('bin/bc-os/evolution_engine.py', '.omo/state/evolution-rollouts.json'),
        ('bin/bc-os/evolution_engine.py', '.omo/state/knowledge-shadow.json'),
        ('bin/bc-os/evolution_engine.py', '.omo/state/routed-signals.json'),
        ('bin/bc-os/north_star_meter_v2.py', '.omo/state/consumption-events.json'),
        ('bin/bc-os/north_star_meter_v3.py', '.omo/state/agent-tick-daemon.jsonl'),
        ('bin/bc-os/north_star_meter_v3.py', '.omo/state/autoloop-trace.jsonl'),
        ('bin/bc-os/north_star_meter_v3.py', '.omo/state/history/health.jsonl'),
        ('bin/bc-os/north_star_meter_v4.py', '.omo/state/agent-tick-daemon.jsonl'),
        ('bin/bc-os/north_star_meter_v4.py', '.omo/state/autoloop-trace.jsonl'),
        ('bin/bc-os/north_star_meter_v4.py', '.omo/state/history/health.jsonl'),
        ('bin/bc-os/north_star_meter_v4.py', '.omo/state/lora-replay-buffer.jsonl'),
        ('bin/bc-os/north_star_meter_v4.py', '.omo/state/tracked-tasks.json'),
        ('bin/bc-os/north_star_meter_v4.py', 'runtime/kv_cache_stats.json'),
        ('bin/bc-os/signal_router.py', '.omo/state/routed-signals.json'),
        ('bin/bc-os/weekly-value-report.py', '.omo/state'),
        ('bin/calibration-sample.py', 'runtime/ssot-stable/journey-runner.py'),
        ('bin/collab/export-dualtrack.py', '.omo/state/collab-dualtrack.yaml'),
        ('bin/delivery/physical_recovery.py', 'runtime'),
        ('bin/e2e-verify-phase2.py', 'runtime/ssot-stable/journey-runner.py'),
        ('bin/gac/adaptive-gate.py', '.omo/state/metrics-store.jsonl'),
        ('bin/gac/agent-presence.py', 'runtime/agents'),
        ('bin/gac/agent-presence.py', 'runtime/coordination'),
        ('bin/gac/alert-router.py', '.omo/state/anomaly-events.jsonl'),
        ('bin/gac/anomaly-detector.py', '.omo/state/anomaly-events.jsonl'),
        ('bin/gac/anomaly-detector.py', '.omo/state/metrics-store.jsonl'),
        ('bin/gac/anti-pattern-detector.py', '.omo/state/agent-tick-daemon.jsonl'),
        ('bin/gac/architecture-check.py', '.omo/state/system.yaml'),
        ('bin/gac/ast-blast-radius.py', 'runtime/omo/architecture_graph.sqlite3'),
        ('bin/gac/ast-index-bootstrap.py', 'runtime/omo/architecture_graph.sqlite3'),
        ('bin/gac/auto-evolution-engine.py', '.omo/state/auto-evolution-state.json'),
        ('bin/gac/auto-evolution-engine.py', '.omo/state/evolution-proposals.json'),
        ('bin/gac/auto-fix-loop.py', '.omo/state/agent-cell/cell_states.json'),
        ('bin/gac/auto-remediate.py', '.omo/state/health.yaml'),
        ('bin/gac/bridge-runtime.py', '.omo/state/bridge-runtime.json'),
        ('bin/gac/check-adversarial-effectiveness.py', '.omo/state/collab-dualtrack.yaml'),
        ('bin/gac/check-dual-track-purity.py', '.omo/state/collab-dualtrack.yaml'),
        ('bin/gac/check-gateway-status-doc.py', '.omo/state'),
        ('bin/gac/check-main-workspace-commit.py', 'runtime/logs/main-workspace-commit-overrides.jsonl'),
        ('bin/gac/check-silent-loss.py', '.omo/state/collab-dualtrack.yaml'),
        ('bin/gac/check-swarm-collision.py', '.omo/state/swarm/active-nodes.yaml'),
        ('bin/gac/ci-local-fast.py', 'runtime/agents'),
        ('bin/gac/convergence-pulse.py', '.omo/state'),
        ('bin/gac/convergence-pulse.py', '.omo/state/pipeline-supervisor-state.json'),
        ('bin/gac/convergence-pulse.py', '.omo/state/tailscale-heartbeat.json'),
        ('bin/gac/cross-domain-trend.py', '.omo/state/runtime/cross-domain-trend.json'),
        ('bin/gac/debt-predictor.py', '.omo/state/governance-predictions.yaml'),
        ('bin/gac/debt-predictor.py', '.omo/state/metrics-store.jsonl'),
        ('bin/gac/decision-inbox-sla.py', '.omo/state/decision-inbox.json'),
        ('bin/gac/decision-inbox-sla.py', '.omo/state/decision-sla-metrics.json'),
        ('bin/gac/devil-chaos-runner.py', 'runtime/omo/architecture_graph.sqlite3'),
        ('bin/gac/gac-compute-onboard.py', 'runtime/litellm/config.yaml'),
        ('bin/gac/gac-local-gate.py', '.omo/state/metrics-store.jsonl'),
        ('bin/gac/governance-health-monitor.py', '.omo/state/governance-health-history.json'),
        ('bin/gac/governance-orchestrator.py', '.omo/state/governance-orchestrator-state.json'),
        ('bin/gac/health-trend-chart.py', '.omo/state/history/health.jsonl'),
        ('bin/gac/keeper-subtraction-engine.py', '.omo/state'),
        ('bin/gac/knowledge-foundry-cron.py', 'runtime/omo/_delivery/foundry'),
        ('bin/gac/metrics-store.py', '.omo/state/metrics-store.jsonl'),
        ('bin/gac/omo-runtime-stamp-policy.py', 'runtime'),
        ('bin/gac/pipeline-orchestrator.py', '.omo/state/pipeline-state.jsonl'),
        ('bin/gac/predictive-governance.py', '.omo/state/metrics-store.jsonl'),
        ('bin/gac/predictive-governance.py', '.omo/state/runtime/predictive-governance.json'),
        ('bin/gac/recommendation-tracker.py', '.omo/state/recommendation-tracker.jsonl'),
        ('bin/gac/remediation-engine.py', '.omo/state/health.yaml'),
        ('bin/gac/remediation-engine.py', '.omo/state/history/uhs.jsonl'),
        ('bin/gac/retro-reference-engine.py', '.omo/state/retro-reference-metrics.json'),
        ('bin/gac/rotate-history.py', '.omo/state/history/health.jsonl'),
        ('bin/gac/rule-vitality-tracker.py', '.omo/state/rule-vitality.jsonl'),
        ('bin/gac/scene-journey-connector.py', '.omo/state/scene-journey-map.json'),
        ('bin/gac/self-evolution-loop.py', '.omo/state/self-evolution-loop.json'),
        ('bin/gac/session-handoff.py', '.omo/state/handoffs'),
        ('bin/gac/signal-scene-connector.py', '.omo/state/signal-scene-state.json'),
        ('bin/gac/swarm-activity-dashboard.py', '.omo/state/lock-graph.json'),
        ('bin/gac/swarm-e2e-scenario.py', 'runtime/omo/architecture_graph.sqlite3'),
        ('bin/gac/uhs-dashboard.py', '.omo/state/history/uhs.jsonl'),
        ('bin/gac/unified-health-score.py', '.omo/state/history/uhs.jsonl'),
        ('bin/gac/unified-orchestrator.py', '.omo/state/orchestrator-state.json'),
        ('bin/gac/value-tracker.py', '.omo/state/north-star-input.json'),
        ('bin/gac/value-tracker.py', '.omo/state/value-executions.json'),
        ('bin/gac/weekly-evolution-report.py', '.omo/state/weekly-evolution-report.json'),
        ('bin/gac/workspace-wip-guard.py', 'runtime/wip-snapshots'),
        ('bin/mof/m2-ssot-inventory.py', '.omo/state/<fstr>'),
        ('bin/ops/alert.py', 'runtime/logs'),
        ('bin/ops/alert.py', 'runtime/pids/<fstr>'),
        ('bin/ops/catalog_api.py', 'runtime/logs'),
        ('bin/ops/catalog_api.py', 'runtime/pids'),
        ('bin/ops/cli.py', 'runtime/logs'),
        ('bin/ops/cli.py', 'runtime/pids'),
        ('bin/ops/cost_tracker.py', 'runtime/pids/<fstr>'),
        ('bin/ops/health-check-cron.py', 'runtime/logs'),
        ('bin/ops/health-check-cron.py', 'runtime/pids'),
        ('bin/ops/monitor_daemon.py', 'runtime/logs'),
        ('bin/ops/monitor_daemon.py', 'runtime/pids'),
        ('bin/ops/runbook.py', 'runtime/logs/<fstr>'),
        ('bin/ops/runbook.py', 'runtime/pids/<fstr>'),
        ('bin/ops/slo_tracker.py', 'runtime/pids/<fstr>'),
        ('bin/ops/smart_alert.py', 'runtime/pids/<fstr>'),
        ('bin/ops/unified_metrics.py', 'runtime/pids/<fstr>'),
        ('bin/panorama/panorama-collect.py', '.omo/state/a2a-messages.jsonl'),
        ('bin/panorama/panorama-collect.py', '.omo/state/agent-cell/cell_states.json'),
        ('bin/panorama/panorama-collect.py', '.omo/state/agent-cell/semantic/roles.jsonl'),
        ('bin/panorama/panorama-collect.py', '.omo/state/agent-tick-daemon.jsonl'),
        ('bin/panorama/panorama-collect.py', '.omo/state/evolution-proposals/*'),
        ('bin/panorama/panorama-collect.py', '.omo/state/handoffs/*'),
        ('bin/panorama/panorama-collect.py', '.omo/state/health.yaml'),
        ('bin/panorama/panorama-collect.py', '.omo/state/mos/theta-facts.json'),
        ('bin/panorama/panorama-collect.py', '.omo/state/pipeline-events.jsonl'),
        ('bin/panorama/panorama-collect.py', '.omo/state/signal-poller-state.json'),
        ('bin/panorama/panorama-collect.py', '.omo/state/value-baselines'),
        ('bin/panorama/panorama-collect.py', 'runtime/cron/remote-hygiene.log'),
        ('bin/panorama/panorama-collect.py', 'runtime/dashboard'),
        ('bin/panorama/panorama-collect.py', 'runtime/dashboard/data.json'),
        ('bin/panorama/panorama-serve.py', 'runtime/dashboard'),
        ('bin/panorama/sunset_redirector.py', 'runtime/dashboard/data.json'),
        ('bin/plan/bet-ledger.py', 'runtime/omo/human-attestation-allowed-signers'),
        ('bin/reports/quarterly-report.py', '.omo/state/health.yaml'),
        ('bin/ssot/agent-cell-pool-live-smoke.py', '.omo/state/agent-cell/cell_states.json'),
        ('bin/ssot/agent-cell-semantic-smoke.py', '.omo/state/agent-cell/semantic'),
        ('bin/ssot/auto-pruner.py', '.omo/state/heartbeats'),
        ('bin/ssot/auto-pruner.py', 'runtime/dashboard/agent-brief.json'),
        ('bin/ssot/drift-face-detector.py', '.omo/state/heartbeats'),
        ('bin/ssot/drift-face-detector.py', 'runtime/dashboard/agent-brief.json'),
        ('bin/ssot/episode-source-aggregator.py', '.omo/state'),
        ('bin/ssot/episode-source-aggregator.py', '.omo/state/heartbeats'),
        ('bin/ssot/knowledge-shadow-runner.py', '.omo/state/knowledge-shadow.json'),
        ('bin/ssot/log-rotate.py', 'runtime/logs'),
        ('bin/ssot/north-star-weekly.py', '.omo/state/north-star-weekly.jsonl'),
        ('bin/ssot/observability-events.py', '.omo/state/metrics-store.jsonl'),
        ('bin/ssot/observability-events.py', '.omo/state/observability-adapters'),
        ('bin/ssot/problem-detector.py', '.omo/state/problem-detector-last.json'),
        ('bin/ssot/problem-detector.py', '.omo/state/system_health.yaml'),
        ('bin/ssot/scene-daemon.py', '.omo/state/scene-daemon-state.jsonl'),
        ('bin/ssot/scene-history.py', 'runtime/backups'),
        ('bin/ssot/service-keeper.py', 'runtime/agora-sse.log'),
        ('bin/ssot/service-keeper.py', 'runtime/cockpit-dashboard.log'),
        ('bin/ssot/service-keeper.py', 'runtime/kos-api.log'),
        ('bin/ssot/value-operator-doctor.py', '.omo/state/value-baselines'),
        ('bin/ssot/value-operator-doctor.py', '.omo/state/value-baselines/value-recorder-baseline-20260919-unique-exec.json'),
        ('bin/ssot/value-recorder.py', '.omo/state/value-baselines'),
        ('bin/ssot/weekly-review.py', '.omo/state/heartbeats'),
        # ── 2026-11-06 BET-Y2Q4-T10-289 AC-02：排除面改按族后入账的 20 处 ──────────────
        # 站点全部先前就有，「不计」是 marker 前缀排除造成的，不是它们合规。规则照旧 shrink_only：
        # 还掉一处 = 删这一行 **且**把那个脚本的根改到缝上（调用时刻解析），二者不同次交付。
        # 分组注释按 spec §2 的三桶；`_knowledge` 13 处里模块级常量 10 / 函数内 3（AC-03 分流）。
        ('bin/bc-os/north_star_meter_v3.py', '.omo/_knowledge/workflow-mesh/events.jsonl'),
        ('bin/bc-os/north_star_meter_v4.py', '.omo/_knowledge/workflow-mesh/events.jsonl'),
        ('bin/bc-os/proposal-triage.py', '.omo/_knowledge/evolution-proposals'),
        ('bin/gac/event-loop-lint.py', '.omo/_knowledge/omo-events.jsonl'),
        ('bin/panorama/panorama-collect.py', '.omo/_knowledge/workflow-mesh/events.jsonl'),
        ('bin/panorama/panorama-collect.py', '.omo/_knowledge/decision-proposals'),
        ('bin/ssot/decision-agent.py', '.omo/_knowledge/evolution-proposals'),
        ('bin/ssot/event-ingest-adapter.py', '.omo/_knowledge/workflow-mesh/events.jsonl'),
        ('bin/ssot/evolution-agent.py', '.omo/_knowledge/evolution-proposals'),
        ('bin/ssot/knowledge-sediment.py', '.omo/_knowledge/sediment'),
        ('bin/ssot/resident-orchestrator-daemon.py', '.omo/_knowledge/workflow-mesh/events.jsonl'),
        ('bin/ssot/scene-evolution-loop.py', '.omo/_knowledge/evolution-proposals'),
        ('bin/ssot/system-health-check.py', '.omo/_knowledge/workflow-mesh/events.jsonl'),
        # `.omo/_delivery` 6 处 + `.omo/_truth` 1 处：同一判据在另两个混合面上的连带命中。
        ('bin/panorama/panorama-collect.py', '.omo/_delivery/observability/events.jsonl'),
        ('bin/ssot/alert-forwarder.py', '.omo/_delivery/alert-forwarder/watermark.json'),
        ('bin/ssot/alert-forwarder.py', '.omo/_delivery/observability/events.jsonl'),
        ('bin/ssot/event-ingest-adapter.py', '.omo/_delivery/event-ingest/watermark.json'),
        ('bin/ssot/observability-events.py', '.omo/_delivery/observability/events.jsonl'),
        ('bin/ssot/personal-signals-adapter.py', '.omo/_delivery/personal-signals/watermark.json'),
        ('bin/gac/check-test-host-hygiene.py', '.omo/_truth/task-center/dispatches'),
    ]
)

Site = tuple[str, int, str, str]  # (仓库相对文件, 行号, marker, 整条拼接路径)


def _split_chain(node: ast.BinOp) -> tuple[ast.AST, list[str]]:
    """拆一条 `/` 链：返回(最左端节点, 各段的文本表示)。只由调用方对最外层链调用。"""
    segments: list[ast.expr] = []
    cur: ast.AST = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        segments.append(cur.right)
        cur = cur.left
    segments.reverse()
    rendered: list[str] = []
    for seg in segments:
        if isinstance(seg, ast.Constant) and isinstance(seg.value, str):
            rendered.append(seg.value)
        elif isinstance(seg, ast.JoinedStr):
            rendered.append("<fstr>")
        elif isinstance(seg, ast.Name):
            rendered.append(f"<var:{seg.id}>")
        else:
            rendered.append("<expr>")
    return cur, rendered


def _literal_prefix(rendered: list[str]) -> str:
    """去掉变量段后的字面量前缀：首个非字面量段即止（spec §3 判据③）。"""
    literals = []
    for seg in rendered:
        if seg.startswith(("<var", "<expr", "<fstr")):
            break
        literals.append(seg)
    return "/".join(literals)


def _checkout_root_aliases(tree: ast.Module) -> set[str]:
    """模块级由含 `__file__` 的赋值绑定的名字（名字派生的检出根别名）。"""
    names = set()
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and "__file__" in ast.dump(node.value)
        ):
            names.add(node.targets[0].id)
    return names


def scan_checkout_pinned_sites(root: Path, markers: tuple[str, ...] = ALL_MARKERS) -> list[Site]:
    """按 spec §3 三条判据扫描 `root/bin/**/*.py`，返回带 marker 分类的站点。"""
    bin_dir = root / "bin"
    if not bin_dir.is_dir():
        return []
    sites: list[Site] = []
    seen: set[tuple[str, int]] = set()
    for path in sorted(bin_dir.rglob("*.py")):
        if set(path.relative_to(bin_dir).parts) & SKIP_SEGMENTS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue
        aliases = _checkout_root_aliases(tree)
        # "最外层链"= 不是任何 Div 节点左操作数的 Div 节点。反过来写（left 是 Div 就跳过）会把
        # 每条链都截到只剩第一段 —— spec §3 的原句正是这个陷阱，2026-10-13 由本文件用例抓到。
        inner = {
            id(node.left)
            for node in ast.walk(tree)
            if isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Div)
            and isinstance(node.left, ast.BinOp)
            and isinstance(node.left.op, ast.Div)
        }
        rel = str(path.relative_to(root))
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
                continue
            if id(node) in inner:
                continue  # 内层链由它所属的最外层链覆盖
            base, rendered = _split_chain(node)
            pinned = ("__file__" in ast.dump(base)) or (
                isinstance(base, ast.Name) and base.id in aliases
            )
            if not pinned:
                continue
            joined = _literal_prefix(rendered)
            marker = next(
                (m for m in markers if joined == m or joined.startswith(m + "/")), None
            )
            if marker is None or (rel, node.lineno) in seen:
                continue
            seen.add((rel, node.lineno))
            sites.append((rel, node.lineno, marker, "/".join(rendered)))
    return sites


def is_gated(site: Site) -> bool:
    """单个站点进门禁集合的判据 —— `gated_pairs` 与读数对拍用例共用这一份，不写两遍。"""
    _, _, marker, whole = site
    return marker in GATED_MARKERS or _family_of(whole) is not None


def gated_pairs(sites: list[Site]) -> frozenset[tuple[str, str]]:
    """门禁集合 = 整面写目标 marker（`GATED_MARKERS`）∪ 落在登记 state 族下的其余站点。

    后半句是 BET-Y2Q4-T10-289 AC-02 的改法：混合面上的站点**一律由同一次扫描分类出来**（可见），
    只有落在具体族下的才计（不计的仍是 62 桶里的一员，`test_one_scan_reproduces_the_spec_readings`
    的分桶读数不变就是这件事的证据）。反过来把族串加进 `ALL_MARKERS` 或按 `.omo/_knowledge`
    整串计，都会让 `test_detector_does_not_fire_on_seam_or_read_plane` 当场红。
    """
    return frozenset((site[0], site[3]) for site in sites if is_gated(site))


def knowledge_bucket(sites: list[Site]) -> dict[str, list[Site]]:
    """`.omo/_knowledge` 的 62 站点按 spec §2 三桶分开：具体族 / 容器本身 / 不在任何族下。

    分桶与 `gated_pairs` 由同一个 `_family_of` 产出（同源），所以「13 处进入计账」和「44 处
    可见不计」不是两份手抄名单，而是同一判据的两个输出。
    """
    out = {"SPECIFIC_FAMILY": [], "CONTAINER": [], "NOT_DECLARED": []}
    for site in sites:
        if site[2] != ".omo/_knowledge":
            continue
        whole = site[3]
        if _family_of(whole) is not None:
            out["SPECIFIC_FAMILY"].append(site)
        elif whole == ".omo/_knowledge":
            out["CONTAINER"].append(site)
        else:
            out["NOT_DECLARED"].append(site)
    return out



# ── AC-01 第四类根：仓内相对锚（落点随进程 CWD） ────────────────────────────
#
# 判据 = `docs/superpowers/specs/2026-11-05-cwd-relative-root-anchor-admission.md` §5 两形：
#   (a) `/`-链的锚既不是 `__file__` 派生、也不是 resolver 或其别名、也不是函数形参，
#       且展平后的字面量部分以 `.omo/` 或 `runtime/` 开头；
#   (b) 单个 `Path(...)` / `os.path.join(...)` 调用，其字面量实参同样以 `.omo/` 或 `runtime/`
#       开头 —— 含 `Path(os.environ.get(NAME, "<仓内相对默认>"))`：env 未声明即默认生效，
#       所以那一形不是「已外置」，是「默认随 CWD」。
# 按 AC-03 走**派生变量链**展平而不是常量名（`STATE_DIR → state_dir → mkdir`），并一跳进
# 本模块的函数体判「这个值是被当根用还是只当后缀拼上去」—— 两种用法在字面量上不可区分，
# 只有用法能区分（`bin/panorama/compact-observation.py` 的 RELATIVE 命名常量就是后缀面）。
# 上面 `scan_checkout_pinned_sites` 的准入谓词（要求 `__file__`）正是 spec §3 第三条失明机制，
# 所以这里是**并列**的第二个检测器而不是把它放宽：钉在检出根的债与随 CWD 的债分桶登记。
RELATIVE_ROOTS = (".omo/", "runtime/")
RELATIVE_CONSTRUCTORS = frozenset({"Path", "join"})
ENV_READERS = frozenset({"get", "getenv"})
ROOT_ACTION_ATTRS = frozenset(
    {
        "mkdir", "write_text", "write_bytes", "read_text", "read_bytes", "touch",
        "unlink", "rmdir", "chmod", "replace", "rename", "glob", "rglob", "iterdir",
        "exists", "is_file", "is_dir", "open", "stat", "resolve", "link_to", "samefile",
    }
)
FS_CALLS = frozenset({"open", "exists", "isfile", "isdir", "makedirs", "mkdir", "remove", "rmtree", "copy", "copyfile"})

RelativeSite = tuple[str, int, str, str]  # (仓库相对文件, 行号, marker, 展平后的相对根)


def _segments(node: ast.AST, bindings: dict[str, ast.AST], seen: frozenset[str] = frozenset()) -> list[str]:
    """按源码顺序展平一条路径表达式的段；判不出来的段记 `*`（后缀比较在此截断）。"""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _segments(node.left, bindings, seen) + _segments(node.right, bindings, seen)
    if isinstance(node, ast.Constant):
        return [node.value] if isinstance(node.value, str) else ["*"]
    if isinstance(node, ast.Name):
        value = bindings.get(node.id)
        if value is None or node.id in seen:
            return ["*"]  # 形参 / 参数进来的根 / 自指 —— 根由调用方决定，不是本表达式的
        return _segments(value, bindings, seen | {node.id})
    if isinstance(node, ast.Call):
        fname = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if fname in ENV_READERS:
            lits = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            return [lits[-1]] if lits else ["*"]  # 末位字面量 = 默认值，它才是未声明时的落点
        if fname == "Path" and len(node.args) == 1:
            return _segments(node.args[0], bindings, seen)
        if fname == "join":
            out: list[str] = []
            for arg in node.args:
                out.extend(_segments(arg, bindings, seen))
            return out
        return ["*"]
    return ["*"]


def _literal_head(segments: list[str]) -> str:
    parts: list[str] = []
    for seg in segments:
        if seg == "*":
            break
        seg = seg.strip("/")
        if seg and seg != ".":
            parts.append(seg)
    return "/".join(parts)


def _relative_root(segments: list[str]) -> str | None:
    head = _literal_head(segments)
    return head if head.startswith(RELATIVE_ROOTS) else None


def _path_bindings(scope: ast.AST) -> dict[str, ast.AST]:
    """`NAME = <expr>` 登记，模块级与函数内都要（AC-03 那条链是**过程内**的）。

    同名重复赋值取按行号的首次：`root = state_root()` 之后 `root = root / "a"` 的根
    由第一次赋值决定，反过来 `x = Path(".omo")` 后 `x = x / "state"` 也是。
    """
    found: list[tuple[int, str, ast.AST]] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and node.value is not None:
                    found.append((node.lineno, t.id, node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            found.append((node.lineno, node.target.id, node.value))
    out: dict[str, ast.AST] = {}
    for _ln, name, value in found:
        out.setdefault(name, value)
    return out


def _leftmost(node: ast.AST) -> ast.AST:
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        node = node.left
    return node


def _parent_map(scope: ast.AST) -> dict[int, ast.AST]:
    par: dict[int, ast.AST] = {}
    for node in ast.walk(scope):
        for child in ast.iter_child_nodes(node):
            par[id(child)] = node
    return par


def _callee_defs(scope: ast.AST) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in ast.walk(scope) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _param_is_root(fn: ast.FunctionDef, param: str, depth: int = 0) -> bool:
    """形参在该函数体里是否被当根用（一跳过程间判据，仍走 AC-03 的用法而非名字）。"""
    return _name_is_root(param, fn, _path_bindings(fn), _parent_map(fn), _callee_defs(fn), depth + 1)


def _name_is_root(
    name: str,
    scope: ast.AST,
    bindings: dict[str, ast.AST],
    par: dict[int, ast.AST],
    defs: dict[str, ast.FunctionDef],
    depth: int = 0,
) -> bool:
    for node in ast.walk(scope):
        if not (isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)):
            continue
        if _expr_is_root(node, scope, par, bindings, defs, depth):
            return True
    return False


def _assign_target_name(node: ast.AST) -> str | None:
    """这个表达式若被直接赋值给一个名字，返回那个名字；多目标/解包/属性赋值 ⇒ None。"""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _expr_is_root(
    node: ast.AST,
    scope: ast.AST,
    par: dict[int, ast.AST],
    bindings: dict[str, ast.AST],
    defs: dict[str, ast.FunctionDef],
    depth: int = 0,
) -> bool:
    """这个路径值是被**当根用**（⇒ 落点由它决定）还是只当后缀拼上去（⇒ 落点由被拼的那棵树决定）。

    判据**只正面枚举**什么用法决定落点（R1 链最左、R2 路径动作的接收者、R3 fs 调用的直接实参、
    R5 一跳进入本模块 callee），其余一律 False。反过来写（默认 True + 逐个摘掉已知的非用法）会
    在每一种没枚举到的父节点形状上假阳 —— 本轮实测两处：`rel.parent in (Path(".omo/_control"), …)`
    的元组透明跳一进到 BoolOp 就落到默认分支，`_resolve_input_path` 里 `path = value or default`
    的默认实参同样落到默认分支，两处都不是落点决策。
    """
    if depth > 3:
        return False
    p = par.get(id(node))
    if p is None:
        return False
    while isinstance(p, (ast.Tuple, ast.List, ast.Set)):
        p = par.get(id(p))  # 容器只是把几份候选并排放，落点由消费容器的东西决定
        if p is None:
            return False
    if isinstance(p, ast.BoolOp):
        target = _assign_target_name(p)
        if target is None:
            return False
        return _name_is_root(target, scope, bindings, par, defs, depth + 1)
    if isinstance(p, ast.Attribute):
        return p.attr in ROOT_ACTION_ATTRS
    if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div):
        if _leftmost(p) is node:
            return True  # R1
        base = _leftmost(p)
        bname = ""
        if isinstance(base, ast.Call):
            bname = base.func.id if isinstance(base.func, ast.Name) else getattr(base.func, "attr", "")
        if bname in RELATIVE_CONSTRUCTORS:
            return _relative_root(_segments(base, bindings)) is not None
        return False  # 拼到检出根 / 缝 / 形参 / 别的名字上 ⇒ 后缀
    if isinstance(p, ast.Call):
        fname = p.func.id if isinstance(p.func, ast.Name) else getattr(p.func, "attr", "")
        if fname in FS_CALLS:
            return True  # R3
        if depth >= 2:
            return False
        fn = defs.get(fname)
        if fn is None:
            return False  # 跨模块的 callee 不在本文件的可见面里 ⇒ 不可判，不猜
        params = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
        received: list[str] = []
        for i, arg in enumerate(p.args):
            if arg is node and i < len(params):
                received.append(params[i])
        for kw in p.keywords:
            if kw.value is node and kw.arg in params:
                received.append(kw.arg)
        return any(_param_is_root(fn, name, depth) for name in received)  # R5
    return False


def scan_cwd_relative_sites(root: Path, shapes: tuple[str, ...] = ("chain", "call")) -> list[RelativeSite]:
    """扫 `root/bin/**/*.py` 的第四类根站点；`shapes` 是变异开关（摘掉一形 ⇒ 该形读数归零）。

    按 (文件, 相对根) 去重取首次命中：登记单位是**根**（`state_root()` 拼接时要裁的是它），
    不是每一行拼接 —— 否则同一处缺陷会按行数被数两遍，且每次加一行拼接都要重签基线。
    """
    bin_dir = root / "bin"
    if not bin_dir.is_dir():
        return []
    rows: list[RelativeSite] = []
    for path in sorted(bin_dir.rglob("*.py")):
        if set(path.relative_to(bin_dir).parts) & SKIP_SEGMENTS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(root))
        bindings = _path_bindings(tree)
        par = _parent_map(tree)
        defs = _callee_defs(tree)
        cands: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                if "chain" not in shapes:
                    continue
                rroot = _relative_root(_segments(_leftmost(node), bindings))
                if rroot is not None:
                    cands.append((node.lineno, rroot))
                continue
            if not isinstance(node, ast.Call) or "call" not in shapes:
                continue
            fname = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if fname not in RELATIVE_CONSTRUCTORS:
                continue
            rroot = _relative_root(_segments(node, bindings))
            if rroot is None:
                continue
            holders = [
                t.targets[0].id
                for t in ast.walk(tree)
                if isinstance(t, ast.Assign) and getattr(t, "value", None) is node
                and len(t.targets) == 1 and isinstance(t.targets[0], ast.Name)
            ]
            if holders and not _name_is_root(holders[0], tree, bindings, par, defs):
                continue  # 只当后缀 ⇒ 这一处不是 CWD 根
            if not holders and not _expr_is_root(node, tree, par, bindings, defs):
                continue
            cands.append((node.lineno, rroot))
        cands.sort(key=lambda x: x[0])
        seen_roots: set[str] = set()
        for lineno, rroot in cands:
            if rroot in seen_roots:
                continue
            marker = next((m for m in ALL_MARKERS if rroot == m or rroot.startswith(m + "/")), None)
            if marker is None:
                continue
            seen_roots.add(rroot)
            rows.append((rel, lineno, marker, rroot))
    return rows


def relative_keys(sites: list[RelativeSite]) -> frozenset[tuple[str, str]]:
    return frozenset((f, rroot) for f, _ln, _m, rroot in sites)


# 2026-11-05 BET-Y2Q4-T10-288 由扫描生成的第四类根登记面：`(文件, 展平后的相对根) -> 为什么它仍是债`。
# 与 BASELINE_WRITESPANE_PAIRS 同构 —— 还掉一处就从这份名单里删掉那行并改掉那个脚本，只减不增。
# 读数口径：按**根**去重（一个文件里同一个根拼多少次都算一处），`.omo/_knowledge` 4 处 / `.omo/_truth` 1 处，
# 另有 1 处是 `_knowledge` 整面（fm_schema_migrate 直接拿 `Path(".omo/_knowledge")` 当遍历根）。
# 2026-11-06 还掉一处：`bin/notification.py` 的 `.omo/_truth/registry/notification-config.yaml`
# （spec §5 AC-02 「`:35` 同形一起处理」）改走 `_config_path() = code_root() / CONFIG_RELATIVE`。
BASELINE_RELATIVE_SITES = {
    ("bin/gac/gate-roi-report.py", ".omo/_knowledge/governance-history.jsonl"): (
        "只读（`load_events(HISTORY)`），未声明根 ⇒ 同一份报告在不同 CWD 下读到不同历史面"
    ),
    ("bin/hitl-proposal.py", ".omo/_knowledge/hitl-proposals"): (
        "HITL 提案面的**生产者**（`create_proposal` / `_save_proposal` 写）。T10-288 只裁了消费者"
        "`bin/notification.py`（env 缺席即拒写），生产者仍随 CWD —— 两半必须同一次交付改，"
        "否则读写分叉比现状更坏（登记在 ADR-0456 addendum 的后续项）"
    ),
    ("bin/ops/continual-harness-refine.py", ".omo/_knowledge/skills"): (
        "写面（`_emit_skills` mkdir 后逐个 skill 落盘）"
    ),
    ("bin/ops/continual-harness-refine.py", ".omo/_knowledge/refinements"): (
        "写面（`run_refine` 里 mkdir 后写 receipt）"
    ),
    ("bin/ssot/auto-bump-doc-governance-budget.py", ".omo/_truth/registry/document-governance.yaml"): (
        "写治理 SSOT registry（`bump_budget`）—— 随 CWD 意味着在 worktree 里跑就改那份检出"
    ),
    ("bin/ssot/fm_schema_migrate.py", ".omo/_knowledge"): (
        "`main` 里拿它当 `rglob('*.md')` 的遍历根，迁移后回写 frontmatter"
    ),
}


def _write(tmp_path: Path, rel: str, source: str) -> Path:
    target = tmp_path / "bin" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return target


def test_scan_target_is_the_checkout_holding_this_test():
    """根不对时不得留下"零站点所以绿"的空绿 —— 先证明扫的是这份检出自己的源码树。"""
    assert BIN_DIR.is_dir(), f"扫描根没有 bin/，ROOT 解析错了: {ROOT}"
    assert (ROOT / "bin" / "plan" / "bet-ledger.py").is_file()
    assert len(list(BIN_DIR.rglob("*.py"))) > 200


def test_one_scan_reproduces_the_spec_readings():
    """ISC-1：spec §1 的桶读数与本文件的基线由同一次扫描产出（同源，不是两份手抄名单）。"""
    sites = scan_checkout_pinned_sites(ROOT)
    buckets: dict[str, int] = {}
    for _, _, marker, _ in sites:
        buckets[marker] = buckets.get(marker, 0) + 1
    assert buckets == SPEC_MARKER_READINGS, f"分类读数与 spec §1 分叉: {buckets}"

    gated = [s for s in sites if is_gated(s)]
    pairs = gated_pairs(sites)
    assert len(gated) == SPEC_GATED_SITES
    assert len(pairs) == SPEC_GATED_PAIRS
    assert len({f for f, _ in pairs}) == SPEC_GATED_FILES


def test_gated_pairs_are_exactly_the_reviewed_baseline():
    """ISC-4：双向相等。新增一处 ⇒ 红；还掉一处不删名单 ⇒ 红。"""
    measured = gated_pairs(scan_checkout_pinned_sites(ROOT))
    new_debt = sorted(measured - BASELINE_WRITESPANE_PAIRS)
    paid_off = sorted(BASELINE_WRITESPANE_PAIRS - measured)
    assert not new_debt, (
        "新增把写面钉在检出根的站点（把 profile 写目标接回 state_root 才是修路；"
        f"登记它需具名理由）: {new_debt}"
    )
    assert not paid_off, (
        "这些站点已经不在实测集合里了 —— 改掉一处就把 BASELINE_WRITESPANE_PAIRS "
        f"的那一行一起删掉（shrink_only）: {paid_off}"
    )
    assert measured == BASELINE_WRITESPANE_PAIRS


def test_detector_fires_on_both_pinned_shapes(tmp_path):
    """ISC-2 自证：名字派生与内联派生两种形状都必须点名（§7⑧ 的漏认形状）。"""
    _write(
        tmp_path,
        "named.py",
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[2]\n"
        'TARGET = WORKSPACE / ".omo/state" / "x.json"\n',
    )
    _write(
        tmp_path,
        "inline.py",
        "from pathlib import Path\n"
        'OUT = Path(__file__).resolve().parents[2] / "runtime" / "y.json"\n',
    )
    found = {(f, m) for f, _, m, _ in scan_checkout_pinned_sites(tmp_path)}
    assert found == {("bin/named.py", ".omo/state"), ("bin/inline.py", "runtime")}, found


def test_detector_renders_the_whole_chain_not_just_its_first_segment(tmp_path):
    """链必须整条渲染：`ROOT / ".omo" / "state" / x` 与 `ROOT / ".omo/state" / x` 是同一个写目标。

    判据原句"只统计最外层链"的实现若写成"`node.left` 是 Div 就跳过"，方向就反了 —— 每条链
    只剩第一段，`.omo` 单独一段匹配不上任何 marker，实测集合当场从 154 掉到 82（2026-10-13
    本文件自证用例抓到的正是这一形）。留这条用例钉住渲染方向。
    """
    _write(
        tmp_path,
        "split.py",
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[2]\n"
        'TARGET = WORKSPACE / ".omo" / "state" / "history.json"\n',
    )
    sites = scan_checkout_pinned_sites(tmp_path)
    assert [(s[2], s[3]) for s in sites] == [(".omo/state", ".omo/state/history.json")], sites


def test_detector_does_not_fire_on_seam_or_read_plane(tmp_path):
    """ISC-3 反过宽：经缝取根不计也不分类；读面两类由同一扫描分类出来但不进门禁集合。"""
    _write(
        tmp_path,
        "seam.py",
        "from pathlib import Path\n"
        "def state_root() -> Path:\n"
        "    return Path('/tmp/state')\n\n"
        'TARGET = state_root() / ".omo/state" / "x.json"\n',
    )
    _write(
        tmp_path,
        "readplane.py",
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[2]\n"
        'REG = ROOT / ".omo/_truth" / "registry" / "y.yaml"\n'
        'DOC = ROOT / ".omo/_knowledge" / "z.md"\n',
    )
    sites = scan_checkout_pinned_sites(tmp_path)
    assert {s[0] for s in sites} == {"bin/readplane.py"}, sites
    assert len(sites) == 2, sites
    assert {s[2] for s in sites} == {".omo/_truth", ".omo/_knowledge"}
    assert gated_pairs(sites) == frozenset()


def test_new_pinned_site_breaks_the_baseline_equality(tmp_path):
    """ISC-4 的反证方向：往一棵只含一处新站点的树里跑判据，结果必须与基线不等（不是⊆就放过）。"""
    _write(
        tmp_path,
        "brand_new.py",
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[2]\n"
        'TARGET = WORKSPACE / ".omo/state" / "brand_new.json"\n',
    )
    measured = gated_pairs(scan_checkout_pinned_sites(tmp_path))
    assert measured == frozenset({("bin/brand_new.py", ".omo/state/brand_new.json")})
    assert measured - BASELINE_WRITESPANE_PAIRS == measured
    assert measured != BASELINE_WRITESPANE_PAIRS


def test_marker_table_is_load_bearing():
    """ISC-1 的反证：摘掉 `.omo/state` 这串 marker，登记面当场缺一大半 —— 基线不是随便抄的。

    2026-11-06 AC-02 之后差额不再只有 `.omo/state*`：靠族表入账的那 20 处，其 marker 一并从分类
    里消失（`scan_checkout_pinned_sites` 按 marker 归类），所以掉的是「`.omo/state` 整面 + 族表
    入账且挂在被摘 marker 上的站点」。两种来源都要能点名，不然「缺一半」这句话会被读成只少了
    一个 marker。
    """
    without_state = scan_checkout_pinned_sites(ROOT, markers=("runtime", "kos"))
    assert gated_pairs(without_state) < BASELINE_WRITESPANE_PAIRS
    dropped = BASELINE_WRITESPANE_PAIRS - gated_pairs(without_state)
    assert dropped and len(dropped) > len(BASELINE_WRITESPANE_PAIRS) // 2, len(dropped)
    assert all(
        p[1].startswith(".omo/state") or _family_of(p[1]) is not None for p in dropped
    ), sorted(p for p in dropped if not p[1].startswith(".omo/state") and not _family_of(p[1]))


# ── AC-02 用测：排除面「按族」而不是「按 marker 前缀」（正反 + 同源 + 变异） ─────
#
# 契约 = `docs/superpowers/specs/2026-11-05-knowledge-plane-root-classification.md` §7 AC-02。
# 四条各管一件事，缺任一条都能让改判据这件事变成假绿：
# ① 13 处具体族站点确实计账（done_when[1] 左半边）；
# ② 容器 5 处 + 未登记 44 处仍由同一次扫描分类出来、但不计（done_when[1] 右半边，
#    也就是「可见不计」不得退化成「不可见」）；
# ③ 合成树上的正反两面，证明**判据本身**认得族与不认得族的差别（不是靠基线抄出来的巧合）；
# ④ 族表承重：把族表清空 ⇒ 读数退回 AC-02 之前，说明那 20 处是族表带来的，不是 marker 表带来的。


def test_family_gate_counts_the_specific_family_knowledge_sites():
    """spec §2 的三分桶在 tip 上必须是 13 / 5 / 44，且 13 处全部进门禁集合。"""
    sites = scan_checkout_pinned_sites(ROOT)
    buckets = knowledge_bucket(sites)
    assert {k: len(v) for k, v in buckets.items()} == {
        "SPECIFIC_FAMILY": 13,
        "CONTAINER": 5,
        "NOT_DECLARED": 44,
    }, {k: len(v) for k, v in buckets.items()}
    gated = gated_pairs(sites)
    specific = {(f, whole) for f, _, _, whole in buckets["SPECIFIC_FAMILY"]}
    assert specific <= gated, f"落具体族的站点没进计账: {sorted(specific - gated)}"
    assert specific <= BASELINE_WRITESPANE_PAIRS, "计账了却没登记 —— shrink_only 名单要同步加行"


def test_family_gate_keeps_container_and_unregistered_planes_visible_but_uncounted():
    """「可见不计」两面：容器本身 5 处 + 不在任何族下 44 处，都在扫描输出里、都不在门禁集合里。

    这条是 AC-02 末句的承重判据 —— 把容器 `.omo/_knowledge` 当成可计族（或把整串 marker 加进
    `GATED_MARKERS`）会当场把它打红，因为那时这 49 处全部进 `gated`。
    """
    sites = scan_checkout_pinned_sites(ROOT)
    buckets = knowledge_bucket(sites)
    uncounted = buckets["CONTAINER"] + buckets["NOT_DECLARED"]
    assert len(uncounted) == 49, len(uncounted)  # 站点口径；同一文件的同名容器会并成一对
    invisible = {(f, whole) for f, _, _, whole in uncounted}
    visible = {(f, whole) for f, _, m, whole in sites if m == ".omo/_knowledge"}
    assert invisible <= visible, "有站点从扫描里消失了 —— 排除面退化成不可见"
    gated = gated_pairs(sites)
    assert not (invisible & gated), sorted(invisible & gated)


def test_family_gate_fires_on_injected_family_not_on_container_child(tmp_path):
    """③ 合成正反：同一种代码形状，只有落在登记族下的那处计账。"""
    _write(
        tmp_path,
        "family.py",
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[2]\n"
        'PROPOSALS = WORKSPACE / ".omo/_knowledge" / "evolution-proposals" / "x.json"\n',
    )
    _write(
        tmp_path,
        "unregistered.py",
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[2]\n"
        'RETROS = WORKSPACE / ".omo/_knowledge" / "retros" / "BET-Y.md"\n',
    )
    _write(
        tmp_path,
        "container.py",
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[2]\n"
        'DOC = WORKSPACE / ".omo/_knowledge"\n',
    )
    sites = scan_checkout_pinned_sites(tmp_path)
    assert len(sites) == 3, sites  # 三处全部分类出来（可见）
    assert gated_pairs(sites) == frozenset(
        {("bin/family.py", ".omo/_knowledge/evolution-proposals/x.json")}
    ), gated_pairs(sites)
    # 「不计」的两处不是被摘出扫描，而是留在桶里：分类 marker 仍是 `.omo/_knowledge`。
    assert {(s[0], s[2]) for s in sites if not is_gated(s)} == {
        ("bin/unregistered.py", ".omo/_knowledge"),
        ("bin/container.py", ".omo/_knowledge"),
    }, sites


def test_family_table_is_load_bearing_and_single_sourced(monkeypatch):
    """④ 族表承重 + 单一来源：清空 `GATEABLE_FAMILIES` ⇒ 门禁读数退回 AC-02 之前（153/143/95）。

    同时反证「容器不作为族参与判定」与「通配项不参与判定」两条筛选都在承重 —— 把它们放回来，
    计账集合会胀到包含合法读面（44 处那一桶），正是 AC-02 禁止的退化方向。
    """
    sites = scan_checkout_pinned_sites(ROOT)
    assert GATEABLE_FAMILIES and ".omo/_knowledge" not in GATEABLE_FAMILIES
    assert not [f for f in GATEABLE_FAMILIES if "*" in f]
    # 单一来源：本文件的族 = 尺 A 文件里那份赋值里的字面量，两处不是手抄。
    parsed = _state_families()
    assert parsed == STATE_FAMILIES and len(parsed) == 42, len(parsed)

    before = gated_pairs(sites)
    monkeypatch.setattr(
        sys.modules[__name__], "GATEABLE_FAMILIES", frozenset(), raising=False
    )
    after = gated_pairs(sites)
    assert after < before, "族表清空后门禁集合没变 —— 说明那 20 处不是族表带来的"
    assert (len(after), len(before)) == (143, 163), (len(after), len(before))



# ── AC-01 第四类根的用测（正反 + 登记双向 + 变异） ────────────────────────────

_RELATIVE_CHAIN_SHAPE = (
    "from pathlib import Path\n"
    'STATE_DIR = Path(".omo")\n\n\n'
    "def emit() -> None:\n"
    '    state_dir = STATE_DIR / "state"\n'
    "    state_dir.mkdir(parents=True, exist_ok=True)\n"
    '    out_file = state_dir / "lock-graph.json"\n'
    '    out_file.write_text("{}")\n'
)

_RELATIVE_CALL_SHAPE = (
    "import os\n"
    "from pathlib import Path\n\n"
    'PROPOSALS = Path(os.environ.get("DEMO_PROPOSALS_DIR", ".omo/_knowledge/demos"))\n\n\n'
    "def load() -> str:\n"
    "    if not PROPOSALS.exists():\n"
    "        return ''\n"
    '    return next(PROPOSALS.glob("*.yaml")).read_text()\n'
)


def test_relative_detector_fires_on_both_relative_shapes(tmp_path):
    """spec §2 两形都要命中：派生变量链（lock_graph 形）与 env 默认值（notification 形）。

    第一形是 AC-03 那条"按派生链展平不按常量名"的正面证据 —— 根锚在 `STATE_DIR`，
    被施加动作的是 `state_dir`，只看常量名或只看动作行都会漏。
    """
    _write(tmp_path, "chain.py", _RELATIVE_CHAIN_SHAPE)
    _write(tmp_path, "envdefault.py", _RELATIVE_CALL_SHAPE)
    found = {(f, rroot) for f, _, _, rroot in scan_cwd_relative_sites(tmp_path)}
    assert found == {
        ("bin/chain.py", ".omo/state"),
        ("bin/envdefault.py", ".omo/_knowledge/demos"),
    }, found


def test_relative_detector_does_not_fire_on_seam_checkout_or_suffix(tmp_path):
    """反过宽四条：经缝取根 / 挂检出根 / 当后缀拼到别人的根上 / 只进谓词比较，都不算第四类根。

    后两形是本轮实测的假阳源（`bin/panorama/compact-observation.py` 的 `DEFAULT_RELATIVE_OUTPUT`
    与 `bin/ssot/check-cross-refs.py` 的 `rel.parent in (Path(".omo/_truth"), …)`），
    判据只能看用法不能看字面量。同时断言第一把尺**仍然**看见那处检出根站点 ——
    收窄第四类不得把已有的钉根债读成不存在（spec §5 AC-01 的反证不退化）。
    """
    _write(
        tmp_path,
        "seam.py",
        "from pathlib import Path\n"
        "def state_root() -> Path:\n"
        "    return Path('/tmp/state')\n\n\n"
        'TARGET = state_root() / ".omo/state" / "x.json"\n'
        "TARGET.write_text('')\n",
    )
    _write(
        tmp_path,
        "checkout.py",
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[2]\n"
        'TARGET = WORKSPACE / ".omo/state" / "y.json"\n'
        "TARGET.write_text('')\n",
    )
    _write(
        tmp_path,
        "suffix.py",
        "from pathlib import Path\n"
        'DEFAULT_RELATIVE_OUTPUT = ".omo/_knowledge/compact/observation.md"\n\n\n'
        "def write_out(root: Path) -> None:\n"
        "    target = root / DEFAULT_RELATIVE_OUTPUT\n"
        "    target.write_text('')\n",
    )
    _write(
        tmp_path,
        "predicate.py",
        "from pathlib import Path\n"
        "def interesting(rel: Path) -> bool:\n"
        "    return rel.parent in (Path(\".omo/_control\"), Path(\".omo/_truth\"))\n",
    )
    _write(
        tmp_path,
        "defaultarg.py",
        "from pathlib import Path\n"
        'DEFAULT_SCENARIO_DIR = Path(".omo/_knowledge/contracts")\n\n\n'
        "def _resolve(root: Path, value, default: Path) -> Path:\n"
        "    path = value or default\n"
        "    return path if path.is_absolute() else root / path\n\n\n"
        "def main() -> Path:\n"
        "    return _resolve(Path('/tmp'), None, DEFAULT_SCENARIO_DIR)\n",
    )
    assert relative_keys(scan_cwd_relative_sites(tmp_path)) == frozenset()
    pinned = gated_pairs(scan_checkout_pinned_sites(tmp_path))
    assert ("bin/checkout.py", ".omo/state/y.json") in pinned, pinned


def test_relative_sites_are_the_reviewed_register():
    """双向相等 + 每条理由指向真实文件：新增一处 ⇒ 红；还掉一处不删名单 ⇒ 红。"""
    measured = relative_keys(scan_cwd_relative_sites(ROOT))
    assert measured == frozenset(BASELINE_RELATIVE_SITES), {
        "new_debt": sorted(measured - frozenset(BASELINE_RELATIVE_SITES)),
        "paid_off_not_removed": sorted(frozenset(BASELINE_RELATIVE_SITES) - measured),
    }
    for (rel, _root), reason in BASELINE_RELATIVE_SITES.items():
        assert (ROOT / rel).is_file(), rel
        assert len(reason) > 12, (rel, reason)


def test_relative_category_is_load_bearing(tmp_path):
    """变异对照：摘掉一形 ⇒ 该形**独立承重的那一处**当场消失。

    合成树是主证据：`Path(".omo") / "state" / file` 只有链形看得见（`Path(".omo")`
    单独一形的 head 是 `.omo`，不在 `RELATIVE_ROOTS` 前缀内）；`Path(os.environ.get(N, ".omo/…"))`
    的根只有调用形看得见（那个文件里没有任何 `/` 链）。两形各自归零一次，才是两形。

    真实树这一面（`bin/**`）的读数是 2026-11-06 复算的量：**调用形覆盖全部 6 处，链形只覆盖 4 处**，
    差的那两处是"根锚只被施加动作、从不参与 `/` 拼接"的形状。链形今天在 `bin/**` 上不是必需项，
    但 spec §2 站点①（`projects/omo/.../lock_graph.py` 的 `STATE_DIR / "state" / file`）正是它唯一
    能认的形状 —— 摘掉链形就等于把第四类根的第一条确证证据判成不存在。
    """
    _write(tmp_path, "chain.py", _RELATIVE_CHAIN_SHAPE)
    _write(tmp_path, "envdefault.py", _RELATIVE_CALL_SHAPE)
    both_keys = {
        "chain": ("bin/chain.py", ".omo/state"),
        "call": ("bin/envdefault.py", ".omo/_knowledge/demos"),
    }
    for shape, other in (("chain", "call"), ("call", "chain")):
        assert relative_keys(scan_cwd_relative_sites(tmp_path, shapes=(shape,))) == {both_keys[shape]}
        assert both_keys[other] not in relative_keys(scan_cwd_relative_sites(tmp_path, shapes=(shape,)))
    assert relative_keys(scan_cwd_relative_sites(tmp_path, shapes=())) == frozenset()

    measured = relative_keys(scan_cwd_relative_sites(ROOT))
    assert relative_keys(scan_cwd_relative_sites(ROOT, shapes=("call",))) == measured
    assert measured - relative_keys(scan_cwd_relative_sites(ROOT, shapes=("chain",))) == {
        ("bin/gac/gate-roi-report.py", ".omo/_knowledge/governance-history.jsonl"),
        ("bin/ssot/auto-bump-doc-governance-budget.py", ".omo/_truth/registry/document-governance.yaml"),
    }

