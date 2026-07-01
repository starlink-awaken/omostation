#!/usr/bin/env python3
"""governance-alert-dispatch: 消费 governance-alerts.yaml::rules 的 X1-X4 告警 dispatcher.

治本 (ISC-4): governance-alerts.yaml 定义了 X1-X4 critical/high 规则, 但此前
无执行器消费它 (log 渠道写 /tmp/governance-alerts.log 从未生成 — 纸面配置).
本 dispatcher 桥接 rules 到已有的 omo event 持久化管道 (alert-aggregator P65-P70):

  1. 读 .omo/_truth/registry/governance-alerts.yaml::rules
  2. 对每条 enabled rule, 用对应 evaluator 求 condition
  3. 命中 → 调 `omo event emit` (走 broker, 合规, 复用 alert-aggregator 持久化模式)
  4. --dry-run 打印每条 rule 的求值结果 (hit/miss/unsupported), 不 emit

condition evaluator (按数据源可用性渐进注册):
  - debt_weight < X      → system.yaml::debt_weight
  - debt_health < X      → system.yaml::debt_metrics.debt_health
  - critical_count > 0   → _truth/registry/debt.yaml severity=critical 未解项
  - missing_githooks > 0 → 扫 .git/hooks/ 非 sample 钩子计数
  - fail / warn (X1 原始) → unsupported (需 X1 实时执行器接入点, 标 skip + warn)
  - ci_count < N         → unsupported (需 CI 探测器)
  - sla_violated         → unsupported (需 SLA 追踪器)

治本原则: 未实现的 condition 不静默跳过 — 显式 warn "unsupported condition",
让 ISC-6 (alert-coverage lint) 能检测 "rule 存在但无 evaluator" 的覆盖缺口.

用法:
  python bin/governance-alert-dispatch.py --dry-run     # 求值 + 打印, 不 emit
  python bin/governance-alert-dispatch.py                # 求值 + 命中调 omo event emit
  python bin/governance-alert-dispatch.py --self-test    # 人为低阈值验证 emit 链路
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
ALERTS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-alerts.yaml"
SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"
DEBT_REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "debt.yaml"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_yaml(path: Path) -> dict | None:
    """加载 yaml, 处理 _truth/ 多文档结构 (AGENTS.md §8: safe_load_all 取正文).

    _truth/ registry yaml 是 frontmatter + 正文双文档 (--- 分隔).
    safe_load 遇多文档报错; safe_load_all 取最后一个非空 dict 作为正文.
    单文档 yaml 同样工作 (返回唯一文档).
    """
    if not path.is_file():
        return None
    try:
        import yaml  # noqa: PLC0415
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        body: dict | None = None
        for d in docs:
            if isinstance(d, dict):
                body = d  # 取最后一个 dict (正文); frontmatter 被覆盖
        return body
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  load {path} failed: {e}", file=sys.stderr)
        return None


def _load_alert_rules(path: Path) -> list[dict]:
    """从 governance-alerts.yaml 提取 rules 段 (容错: 文件 yaml 语法损坏).

    治本障碍 (ISC-NEW): governance-alerts.yaml 第 10 行 `> 定义...` 是 markdown
    blockquote 误入 yaml 正文, yaml 将 `>` 解析为 folded scalar 导致全文件解析
    失败, rules 从未被任何解析器成功读取. 根因修复 (改 `>` → `#`) 需走 omo broker
    (governance-state-mutation, .omo/ 禁直写), 记为 ISC-NEW follow-up.

    本函数用正则提取 `rules:` 段单独 safe_load, 绕过损坏的注释行, 让 dispatcher
    先工作起来. 源文件修复后 (ISC-NEW 完成) 可回退到 _load_yaml.
    """
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^rules:\s*$", text, re.MULTILINE)
    if not m:
        print(f"⚠️  {path} 未找到 'rules:' 段", file=sys.stderr)
        return []
    rules_section = text[m.start():]
    try:
        import yaml  # noqa: PLC0415
        data = yaml.safe_load(rules_section)
        return (data or {}).get("rules") or []
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  {path} rules 段解析失败: {e}", file=sys.stderr)
        return []


# ── condition evaluators ────────────────────────────────────────────────
# 每个 evaluator 返回 (current_value, hit: bool) 或 (None, False) 表示 unsupported.

def _eval_debt_weight(op: str, rhs: float, _ws: Path) -> tuple[object, str]:
    """debt_weight < X → system.yaml::debt_weight (顶层)."""
    data = _load_yaml(SYSTEM_YAML) or {}
    val = data.get("debt_weight")
    if not isinstance(val, (int, float)):
        return (None, "unsupported: debt_weight missing in system.yaml")
    return (val, _apply_op(val, op, rhs))


def _eval_debt_health(op: str, rhs: float, _ws: Path) -> tuple[object, str]:
    """debt_health < X → system.yaml::debt_metrics.debt_health."""
    data = _load_yaml(SYSTEM_YAML) or {}
    val = (data.get("debt_metrics") or {}).get("debt_health")
    if not isinstance(val, (int, float)):
        return (None, "unsupported: debt_metrics.debt_health missing")
    return (val, _apply_op(val, op, rhs))


def _eval_critical_count(op: str, rhs: float, _ws: Path) -> tuple[object, str]:
    """critical_count > 0 → debt.yaml 未解 severity=critical 条目数."""
    data = _load_yaml(DEBT_REGISTRY) or {}
    items = data.get("items") or []
    if not isinstance(items, list):
        return (0, "miss" if not _apply_op(0, op, rhs) else "hit")
    crit = sum(
        1 for it in items
        if isinstance(it, dict)
        and it.get("severity") == "critical"
        and it.get("resolved") is not True
        and it.get("lifecycle_state") != "resolved"
    )
    return (crit, _apply_op(crit, op, rhs))


def _eval_missing_githooks(op: str, rhs: float, ws: Path) -> tuple[object, str]:
    """missing_githooks > 0 → .git/hooks/ 非 sample 钩子缺口."""
    hooks_dir = ws / ".git" / "hooks"
    if not hooks_dir.is_dir():
        return (None, "unsupported: .git/hooks not found (not a git repo?)")
    present = [
        f for f in hooks_dir.iterdir()
        if f.is_file() and not f.name.endswith(".sample")
    ]
    # 期望 pre-commit / pre-push 至少存在
    expected = {"pre-commit", "pre-push"}
    missing = expected - {f.name for f in present}
    return (len(missing), _apply_op(len(missing), op, rhs))


def _eval_overdue_approval(op: str, rhs: float, ws: Path) -> tuple[object, str]:
    """overdue_approval_count > 0 → planned P1 任务 age>14天 且 approval_ref=null (ISC-31).

    治本 ISC-30 流程堵塞: P1 任务卡 planned 无人审批时, age>14天 自动告警.
    当前 5 个 P1 任务 age 5-6 天 (未触发, 预防性); 未来超 14 天 → hit.
    """
    planned_dir = ws / ".omo" / "tasks" / "planned"
    if not planned_dir.is_dir():
        return (0, "miss")
    import yaml  # noqa: PLC0415
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    overdue = 0
    for tf in planned_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(tf.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        if data.get("priority") != "P1" or data.get("approval_ref"):
            continue
        created = str(data.get("created_at", ""))
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created_dt < cutoff:
                overdue += 1
        except Exception:  # noqa: BLE001
            continue
    return (overdue, _apply_op(overdue, op, rhs))


EVALUATORS = {
    "debt_weight": _eval_debt_weight,
    "debt_health": _eval_debt_health,
    "critical_count": _eval_critical_count,
    "missing_githooks": _eval_missing_githooks,
    "overdue_approval_count": _eval_overdue_approval,
}

UNSUPPORTED_SIGNALS = {"fail", "warn", "ci_count", "sla_violated"}


def _apply_op(lhs: float, op: str, rhs: float) -> str:
    """求 lhs op rhs, 返回 'hit' 或 'miss'."""
    if op == "<":
        return "hit" if lhs < rhs else "miss"
    if op == "<=":
        return "hit" if lhs <= rhs else "miss"
    if op == ">":
        return "hit" if lhs > rhs else "miss"
    if op == ">=":
        return "hit" if lhs >= rhs else "miss"
    if op == "==" or op == "=":
        return "hit" if lhs == rhs else "miss"
    return "unsupported: unknown op"


# condition 解析: "debt_weight < 0.6" → metric=debt_weight, op=<, rhs=0.6
_COND_RE = re.compile(r"^\s*(\w+)\s*(<=|>=|==|=|<|>)\s*([0-9.]+)\s*$")


def _parse_condition(cond: str) -> tuple[str, str, float] | None:
    m = _COND_RE.match(cond or "")
    if not m:
        return None
    metric, op, rhs = m.group(1), m.group(2), float(m.group(3))
    return metric, op, rhs


def evaluate_rule(rule: dict, ws: Path) -> dict:
    """求值单条 rule, 返回 {id, dimension, severity, condition, status, current, note}.

    status ∈ {hit, miss, unsupported, error}.
    """
    rid = rule.get("id", "<no-id>")
    dimension = rule.get("dimension", "?")
    severity = rule.get("severity", "?")
    enabled = rule.get("enabled", True)
    cond_str = rule.get("condition", "")

    result = {
        "id": rid, "dimension": dimension, "severity": severity,
        "condition": cond_str, "enabled": enabled,
        "status": "error", "current": None, "note": "",
    }

    if not enabled:
        result["status"] = "disabled"
        return result

    parsed = _parse_condition(cond_str)
    if parsed is None:
        # 非数值表达式 (fail/warn/sla_violated 等)
        metric = cond_str.strip().split()[0] if cond_str else ""
        if metric in UNSUPPORTED_SIGNALS or cond_str in UNSUPPORTED_SIGNALS:
            result["status"] = "unsupported"
            result["note"] = f"signal '{cond_str}' 需实时执行器接入 (X1 审计/CI/SLA), 暂无 evaluator"
        else:
            result["status"] = "error"
            result["note"] = f"unparseable condition: '{cond_str}'"
        return result

    metric, op, rhs = parsed
    evaluator = EVALUATORS.get(metric)
    if evaluator is None:
        result["status"] = "unsupported"
        result["note"] = f"metric '{metric}' 无 evaluator (数据源未实现)"
        return result

    current, status_or_note = evaluator(op, rhs, ws)
    result["current"] = current
    if status_or_note in ("hit", "miss"):
        result["status"] = status_or_note
    else:
        result["status"] = "unsupported"
        result["note"] = status_or_note
    return result


def emit_alert(rule_result: dict, dry_run: bool) -> bool:
    """命中 rule → 调 omo event emit (走 broker). dry_run 时只打印."""
    payload = {
        "rule_id": rule_result["id"],
        "dimension": rule_result["dimension"],
        "severity": rule_result["severity"],
        "condition": rule_result["condition"],
        "current": rule_result["current"],
        "dispatched_at": _utc_now(),
        "source": "governance-alert-dispatch",
    }
    if dry_run:
        print(f"   📤 [dry-run] would emit: governance_alert_dispatched {json.dumps(payload, ensure_ascii=False)}")
        return True
    try:
        subprocess.run(
            ["omo", "event", "emit",
             "--type", "governance_alert_dispatched",
             "--source", "governance-alert-dispatch",
             "--payload", json.dumps(payload, ensure_ascii=False)],
            timeout=10, capture_output=True, check=False,
        )
        print(f"   📤 emitted: governance_alert_dispatched (rule={rule_result['id']})")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"   ❌ emit failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="governance-alert-dispatch: X1-X4 rule dispatcher (ISC-4)")
    parser.add_argument("--dry-run", action="store_true", help="求值 + 打印, 不 emit")
    parser.add_argument("--self-test", action="store_true", help="人为低阈值验证 emit 链路")
    args = parser.parse_args()

    if not ALERTS_YAML.is_file():
        print(f"❌ {ALERTS_YAML} 不存在", file=sys.stderr)
        return 1

    # 容错加载: governance-alerts.yaml 第10行有 markdown > 损坏 yaml (ISC-NEW).
    # 用 _load_alert_rules 提取 rules 段绕过; 源文件修复后可回退 _load_yaml.
    rules = _load_alert_rules(ALERTS_YAML)
    if not rules:
        print(f"⚠️  {ALERTS_YAML} 无 rules (或 yaml 损坏无法提取), 退出")
        return 0

    print(f"🚨 governance-alert-dispatch → {len(rules)} rules")
    print(f"   workspace: {WORKSPACE}")
    print()

    hits, misses, unsupported, disabled, errors = [], [], [], [], []
    for rule in rules:
        if args.self_test:
            # 人为注入会命中的 condition, 验证 emit 链路
            rule = dict(rule)
            rule["condition"] = "debt_health < 999"
            rule["enabled"] = True
        r = evaluate_rule(rule, WORKSPACE)
        sev = r["severity"]
        marker = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(sev, "⚪")
        cur = f" (current={r['current']})" if r["current"] is not None else ""
        note = f" — {r['note']}" if r["note"] else ""
        print(f"  {marker} [{r['dimension']}] {r['id']}: {r['condition']!r} → {r['status']}{cur}{note}")

        if r["status"] == "hit":
            hits.append(r)
            # self-test 也走 dry, 避免验证时产生真实 governance event 副作用 (AGENTS.md: 不主动改 .omo/)
            emit_alert(r, args.dry_run or args.self_test)
        elif r["status"] == "miss":
            misses.append(r)
        elif r["status"] == "unsupported":
            unsupported.append(r)
        elif r["status"] == "disabled":
            disabled.append(r)
        else:
            errors.append(r)

    print()
    print(f"📊 求值汇总: {len(hits)} hit / {len(misses)} miss / {len(unsupported)} unsupported / {len(disabled)} disabled / {len(errors)} error")

    if unsupported:
        print(f"\n⚠️  {len(unsupported)} 条 rule 无 evaluator (ISC-6 alert-coverage lint 应覆盖):")
        for r in unsupported:
            print(f"   - {r['id']}: {r['note']}")

    # exit code: 有 hit 或 error → 非 0 (CI 可感知)
    return 1 if (hits or errors) else 0


if __name__ == "__main__":
    sys.exit(main())
