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
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / "bin"

# 门禁只管这两类（spec §1）。其余四类是读面 / 全机协调桥 / 署名文档面，排除理由见 §1 表。
GATED_MARKERS = (".omo/state", "runtime")
ALL_MARKERS = (".omo/state", ".omo/_delivery", ".omo/_knowledge", ".omo/_truth", "runtime", "kos")
SKIP_SEGMENTS = {"_archive", "_vendored", "__pycache__", ".venv"}

# spec §1 的读数表 —— 与本文件扫描出的分类逐桶相等（同一判据、同一次扫描产出）。
SPEC_MARKER_READINGS = {
    ".omo/_truth": 160,
    ".omo/state": 103,
    ".omo/_delivery": 82,
    "runtime": 51,
    ".omo/_knowledge": 63,
    "kos": 2,
}
SPEC_GATED_SITES = 154
SPEC_GATED_PAIRS = 144
SPEC_GATED_FILES = 95

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
        ('bin/panorama/panorama-collect.py', 'runtime/omo/event-ledger.sqlite3'),
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
        ('bin/ssot/weekly-review.py', '.omo/state/heartbeats'),    ]
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


def gated_pairs(sites: list[Site]) -> frozenset[tuple[str, str]]:
    return frozenset((f, whole) for f, _, m, whole in sites if m in GATED_MARKERS)


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

    gated = [s for s in sites if s[2] in GATED_MARKERS]
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
    """ISC-1 的反证：砍掉 `.omo/state` 这个 marker，登记面当场缺一半 —— 基线不是随便抄的。"""
    without_state = scan_checkout_pinned_sites(ROOT, markers=("runtime", "kos"))
    assert gated_pairs(without_state) < BASELINE_WRITESPANE_PAIRS
    dropped = BASELINE_WRITESPANE_PAIRS - gated_pairs(without_state)
    assert all(p[1].startswith(".omo/state") for p in dropped) and dropped
