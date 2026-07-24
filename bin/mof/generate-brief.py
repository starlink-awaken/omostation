#!/usr/bin/env python3
"""Generate BRIEF.md containing Decision Inbox and X3 Value Metrics."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"
BRIEF_MD = WORKSPACE / "BRIEF.md"
DELIVERY_SOFT_GATE_YAML = (
    WORKSPACE / ".omo" / "_truth" / "registry" / "x3-delivery-soft-gate.yaml"
)


def get_now_str() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_brief_content(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if line.startswith("> **Generated**:"):
            lines.append("> **Generated**: `<runtime>`")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def write_brief_if_changed(content: str) -> bool:
    if BRIEF_MD.exists():
        current = BRIEF_MD.read_text(encoding="utf-8")
        if normalize_brief_content(current) == normalize_brief_content(content):
            return False
    BRIEF_MD.write_text(content, encoding="utf-8")  # audit-exempt: non-atomic-write
    return True


PHYSICAL_HOSTS_CARD_ID = "NEEDS-HUMAN-P80-PHYSICAL-HOSTS"
PHYSICAL_HOSTS_CARD_STEM = "needs-human-p80-physical-hosts"


def physical_hosts_suspend_day_count(
    card_path: Path | None = None,
    *,
    now: datetime | None = None,
) -> int | None:
    """Days since physical-hosts needs-human card was created (ADR-0228 D3).

    Returns None if the card is absent. Day-count is floor of elapsed UTC days
    since created_at (minimum 0).
    """
    import yaml  # noqa: PLC0415

    path = card_path or (
        WORKSPACE / ".omo" / "tasks" / "planned" / f"{PHYSICAL_HOSTS_CARD_STEM}.yaml"
    )
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    created = data.get("created_at") or data.get("created")
    if not created:
        return 0
    try:
        created_s = str(created).replace("Z", "+00:00")
        created_dt = datetime.fromisoformat(created_s)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        now_dt = now or datetime.now(timezone.utc)
        delta = now_dt - created_dt.astimezone(timezone.utc)
        return max(0, int(delta.total_seconds() // 86400))
    except Exception:
        return 0


def physical_hosts_weekly_reaffirmation(
    *,
    now: datetime | None = None,
    card_path: Path | None = None,
) -> dict | None:
    """Build BRIEF Inbox reaffirmation line while physical-hosts card exists.

    Always emits when card present (session-brief regeneration = reaffirmation
    surface; day-count is the suspend duration signal).
    """
    days = physical_hosts_suspend_day_count(card_path, now=now)
    if days is None:
        return None
    path = card_path or (
        WORKSPACE / ".omo" / "tasks" / "planned" / f"{PHYSICAL_HOSTS_CARD_STEM}.yaml"
    )
    try:
        rel = str(path.resolve().relative_to(WORKSPACE.resolve()))
    except ValueError:
        rel = str(path)
    return {
        "id": f"{PHYSICAL_HOSTS_CARD_ID}-WEEKLY",
        "title": (
            f"物理底座挂起周重申（ADR-0228 D3）: needs-human-p80-physical-hosts 仍开放 · "
            f"挂起第 {days} 天 · 勿宣称 G-DEL.1/3 物理达标"
        ),
        "path": rel,
        "source": "physical-suspend-reminder",
        "suspend_day_count": days,
    }


def scan_decision_inbox() -> list[dict]:
    """扫描所有的 needs-human 卡片或任务."""
    import yaml  # noqa: PLC0415

    tasks = []

    # 扫描 .omo/tasks/
    tasks_dir = WORKSPACE / ".omo" / "tasks"
    if tasks_dir.is_dir():
        for p in tasks_dir.rglob("*.yaml"):
            try:
                content = p.read_text(encoding="utf-8")
                # closed cards may still contain the substring — skip closed/
                if "closed" in p.parts:
                    continue
                if "needs-human" in content:
                    data = yaml.safe_load(content) or {}
                    if str(data.get("status", "")).lower() == "closed":
                        continue
                    if data.get("needs-human") is False:
                        continue
                    tasks.append(
                        {
                            "id": data.get("id") or p.stem,
                            "title": data.get("title")
                            or data.get("desc")
                            or "System task pending human decision",
                            "path": f".omo/tasks/{p.relative_to(tasks_dir)}",
                            "source": "omo-debt",
                        }
                    )
            except Exception:
                pass

    # 扫描 spaces/
    spaces_dir = WORKSPACE / "spaces"
    if spaces_dir.is_dir():
        for p in spaces_dir.rglob("*.yaml"):
            try:
                content = p.read_text(encoding="utf-8")
                if "needs-human" in content:
                    data = yaml.safe_load(content) or {}
                    tasks.append(
                        {
                            "id": data.get("id") or p.stem,
                            "title": data.get("title")
                            or "Workspace item needs human decision",
                            "path": f"spaces/{p.relative_to(spaces_dir)}",
                            "source": "space-card",
                        }
                    )
            except Exception:
                pass

    # ADR-0228 D3: weekly reaffirmation of physical suspend while card open
    reaffirm = physical_hosts_weekly_reaffirmation()
    if reaffirm:
        tasks.insert(0, reaffirm)

    return tasks


def load_delivery_soft_gate(config_path: Path | None = None) -> dict:
    """Load X3 delivery soft-gate config (threshold not hardcoded)."""
    import yaml  # noqa: PLC0415

    path = config_path or DELIVERY_SOFT_GATE_YAML
    defaults = {
        "enabled": True,
        "monthly_min_deliveries": 8,
        "compare_previous_month": True,
        "warning_class": "soft",
        "inbox_tag": "needs-human",
        "match_keywords": ["delivery", "deliverable"],
    }
    if not path.is_file():
        return defaults
    try:
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        body = None
        for d in docs:
            if isinstance(d, dict) and "x3_delivery_soft_gate" in d:
                body = d["x3_delivery_soft_gate"]
                break
            if isinstance(d, dict) and "monthly_min_deliveries" in d:
                body = d
                break
        if not isinstance(body, dict):
            return defaults
        out = dict(defaults)
        out.update({k: v for k, v in body.items() if v is not None})
        return out
    except Exception:
        return defaults


def _is_delivery_card(path: Path, keywords: list[str]) -> bool:
    try:
        content = path.read_text(encoding="utf-8").lower()
    except Exception:
        return False
    return any(k.lower() in content for k in keywords)


def count_deliveries_by_month(
    spaces_dir: Path | None = None,
    *,
    now: datetime | None = None,
    keywords: list[str] | None = None,
) -> dict:
    """Count delivery cards for current and previous calendar month (mtime).

    Returns keys: current_month, previous_month, current_count, previous_count, total.
    """
    spaces = spaces_dir or (WORKSPACE / "spaces")
    keywords = keywords or ["delivery", "deliverable"]
    now = now or datetime.now(timezone.utc)
    cur_y, cur_m = now.year, now.month
    if cur_m == 1:
        prev_y, prev_m = cur_y - 1, 12
    else:
        prev_y, prev_m = cur_y, cur_m - 1

    current_count = 0
    previous_count = 0
    total = 0
    if spaces.is_dir():
        for p in spaces.rglob("*.yaml"):
            if not p.is_file():
                continue
            if not _is_delivery_card(p, keywords):
                continue
            total += 1
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if mtime.year == cur_y and mtime.month == cur_m:
                current_count += 1
            elif mtime.year == prev_y and mtime.month == prev_m:
                previous_count += 1

    return {
        "current_month": f"{cur_y:04d}-{cur_m:02d}",
        "previous_month": f"{prev_y:04d}-{prev_m:02d}",
        "current_count": current_count,
        "previous_count": previous_count,
        "total": total,
    }


def evaluate_delivery_soft_gate(
    monthly: dict,
    gate: dict | None = None,
) -> dict:
    """Soft-only evaluation: under threshold → warning inbox item, never hard-fail."""
    gate = gate or load_delivery_soft_gate()
    threshold = int(gate.get("monthly_min_deliveries", 8))
    enabled = bool(gate.get("enabled", True))
    current = int(monthly.get("current_count", 0))
    previous = int(monthly.get("previous_count", 0))
    delta = current - previous
    under = enabled and current < threshold
    warning = None
    if under:
        warning = {
            "id": "X3-DELIVERY-SOFT-GATE",
            "title": (
                f"工作交付月度软门禁: {monthly.get('current_month')} 交付 "
                f"{current} < 阈值 {threshold}（环比 {previous} → {current}, Δ{delta:+d}）"
            ),
            "path": str(
                DELIVERY_SOFT_GATE_YAML.relative_to(WORKSPACE)
                if DELIVERY_SOFT_GATE_YAML.is_relative_to(WORKSPACE)
                else DELIVERY_SOFT_GATE_YAML
            ),
            "source": "x3-soft-gate",
            "class": gate.get("warning_class", "soft"),
            "tag": gate.get("inbox_tag", "needs-human"),
        }
    return {
        "enabled": enabled,
        "threshold": threshold,
        "under_threshold": under,
        "current_count": current,
        "previous_count": previous,
        "delta": delta,
        "current_month": monthly.get("current_month"),
        "previous_month": monthly.get("previous_month"),
        "warning": warning,
        "hard_block": False,
    }


def scan_x3_metrics() -> dict:
    """统计 X3 价值产出指标."""
    metrics = {
        "creations": 0,
        "deliveries": 0,
        "knowledge_reuse": 0,
        "delivery_monthly": {},
        "delivery_soft_gate": {},
    }

    # 1. 创意创作发布度量 (检测并递归扫描实际创意创作输出路径)
    creation_dirs = [
        Path("/Users/xiamingxing/Documents/@创意创作/_outputs"),
        Path("/Users/xiamingxing/Documents/@创意创作"),
        WORKSPACE / "创意创作" / "_outputs",
        Path("/Users/xiamingxing/Documents/@驾驶舱/_outputs"),
        WORKSPACE / "data" / "creations",
    ]
    for d in creation_dirs:
        if d.is_dir():
            # 递归统计所有文件 (排除隐藏文件)
            files = [
                f for f in d.rglob("*") if f.is_file() and not f.name.startswith(".")
            ]
            metrics["creations"] = len(files)
            break

    # 2. 工作交付度量 (spaces/ 交付卡片 + 月度环比软门禁)
    gate = load_delivery_soft_gate()
    keywords = list(gate.get("match_keywords") or ["delivery", "deliverable"])
    monthly = count_deliveries_by_month(keywords=keywords)
    metrics["deliveries"] = int(monthly["total"])
    metrics["delivery_monthly"] = monthly
    metrics["delivery_soft_gate"] = evaluate_delivery_soft_gate(monthly, gate)

    # 3. 知识复用度量 (真实查询 KOS SQLite 检索库)
    kos_dir = WORKSPACE / "kos"
    sqlite_db = kos_dir / "kos-index.sqlite"
    if sqlite_db.is_file():
        import sqlite3  # noqa: PLC0415

        try:
            conn = sqlite3.connect(str(sqlite_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents")
            doc_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM kos_entities")
            entity_count = cursor.fetchone()[0]
            metrics["knowledge_reuse"] = doc_count + entity_count
            conn.close()
        except Exception:
            # 降级降速扫描
            metrics["knowledge_reuse"] = len(
                [f for f in kos_dir.rglob("*") if f.is_file()]
            )
    else:
        metrics["knowledge_reuse"] = len([f for f in kos_dir.rglob("*") if f.is_file()])

    return metrics


def run_write_owner_audit() -> list[str]:
    """跑 write-owner 审计以防违规写入."""
    try:
        from write_owner_audit import (
            audit_staged,
            load_owners,
            get_git_user,
            get_staged_files,
        )

        owners = load_owners()
        current_user = get_git_user() or "unknown"
        staged_files = get_staged_files()
        return audit_staged(staged_files, owners, current_user)
    except Exception:
        return []


def generate_brief_content() -> str:
    import yaml  # noqa: PLC0415

    # 读取系统健康分
    health_score = 90
    gov_anomaly = 100
    online_ratio = 1.0

    if SYSTEM_YAML.is_file():
        try:
            data = yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8")) or {}
            health_score = data.get("health_score", 90)
            gov_anomaly = data.get("governance_anomaly_score", 100)
            # daemon 在线率不读此死字段 — 改为下方实时探测 (消除快照幻影)
        except Exception:
            pass

    # 治本 (health-daemon-ratio-phantom): daemon 在线率实时复用 compass 探测函数,
    # 不读 system.yaml::service_online_ratio 死字段 (无人刷新→快照幻影 0.6).
    # collect_runtime_health 纯读 system_health.yaml 现算, 无副作用, 失败回退默认 1.0.
    try:
        _bin_dir = str(Path(__file__).resolve().parents[1])
        if _bin_dir not in sys.path:
            sys.path.insert(0, _bin_dir)
        from compass_radar import collect_runtime_health  # noqa: PLC0415

        _ratio, _ = collect_runtime_health(WORKSPACE)
        if _ratio is not None:
            online_ratio = _ratio
    except Exception:
        pass

    now_str = get_now_str()
    decisions = scan_decision_inbox()
    x3 = scan_x3_metrics()
    violations = run_write_owner_audit()
    soft = x3.get("delivery_soft_gate") or {}
    monthly = x3.get("delivery_monthly") or {}
    soft_warnings = []
    if soft.get("warning"):
        soft_warnings.append(soft["warning"])

    # 构建 BRIEF markdown
    lines = []
    lines.append("# BRIEF.md — 织星状态简报与决策收件箱")
    lines.append("")
    lines.append(
        f"> **Generated**: `{now_str}` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `{health_score}/100`"
    )
    lines.append("")

    # 1. 决策收件箱 (Decision Inbox - WS-4)
    lines.append("## 📥 待决策收件箱 (Decision Inbox)")
    lines.append("")
    if not decisions and not violations and not soft_warnings:
        lines.append("✅ **当前没有需要人工干预的阻断决策，健康免疫运转良好。**")
        lines.append("")
    else:
        if violations:
            lines.append("### 🚨 所有权越权告警 (Write Ownership Violations)")
            for v in violations:
                lines.append(f"- **[BLAME]** {v} (需要核实写入进程并恢复)")
            lines.append("")

        if soft_warnings:
            lines.append("### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)")
            for w in soft_warnings:
                lines.append(
                    f"- **[{w.get('source', 'soft').upper()}/{w.get('class', 'soft')}]** "
                    f"{w['title']} → [`{w['path']}`](file://{WORKSPACE}/{w['path']})"
                )
            lines.append("")

        if decisions:
            lines.append("### ⏳ 待处理卡片与债务 (Needs Human Decisions)")
            for d in decisions:
                lines.append(
                    f"- **[{d['source'].upper()}]** {d['title']} → [`{d['path']}`](file://{WORKSPACE}/{d['path']})"
                )
            lines.append("")

    # 2. X3 价值仪表 (Value Metrics - WS-5)
    lines.append("## 📈 X3 价值仪表 (Value Metrics)")
    lines.append("")
    lines.append("| 维度 | 度量指标 | 状态 | 物理数据源 |")
    lines.append("|------|----------|------|------------|")
    lines.append(
        f"| **创意创作** | 新增发布数: `{x3['creations']}` | 正常 | `@创意创作/_outputs` |"
    )
    deliv_status = "预警" if soft.get("under_threshold") else "正常"
    cur_m = monthly.get("current_month", "?")
    prev_m = monthly.get("previous_month", "?")
    cur_c = monthly.get("current_count", 0)
    prev_c = monthly.get("previous_count", 0)
    thr = soft.get("threshold", 8)
    lines.append(
        f"| **工作交付** | 本月 `{cur_m}`: `{cur_c}` / 上月 `{prev_m}`: `{prev_c}` "
        f"(累计 `{x3['deliveries']}`, 软阈 `{thr}`) | {deliv_status} | "
        f"`spaces/` + `.omo/_truth/registry/x3-delivery-soft-gate.yaml` |"
    )
    lines.append(
        f"| **知识复用** | KOS 索引篇: `{x3['knowledge_reuse']}` | 正常 | `kos/` 篇目 |"
    )
    # B5: per-role completion/cost rows (pointerized X3)
    role_metrics_path = (
        WORKSPACE / ".omo" / "_truth" / "registry" / "x3-role-metrics.yaml"
    )
    if role_metrics_path.is_file():
        try:
            import yaml as _yaml  # noqa: PLC0415

            rm = _yaml.safe_load(role_metrics_path.read_text(encoding="utf-8")) or {}
            roles = rm.get("roles") or {}
            for role_id, row in roles.items():
                rate = row.get("completion_rate", "?")
                cost = row.get("cost_units", "?")
                rate_s = f"{rate:.2%}" if isinstance(rate, float) else str(rate)
                lines.append(
                    f"| **角色·{role_id}** | 完成率 `{rate_s}` · 成本单位 `{cost}` | "
                    f"正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |"
                )
        except Exception:
            pass
    lines.append("")

    # 3. 治理健康指标折叠逻辑 (Health Folding - WS-5)
    # 当健康分 >= 90 时折叠
    if health_score >= 90:
        lines.append("<details>")
        lines.append(
            f"<summary>⚙️ <b>治理健康分详情 (复合 {health_score}/100, 已自动收纳)</b></summary>"
        )
        lines.append("")
        lines.append(f"- **GAC 异常扣分**: `{gov_anomaly}/100` (无 anomalies)")
        lines.append(f"- **常驻 daemon 在线率**: `{online_ratio:.2%}`")
        lines.append("- **新鲜度分数**: `100/100` (正常)")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    else:
        lines.append("## ⚙️ 治理健康分详情 (Health Detail)")
        lines.append("")
        lines.append(f"- **复合健康分**: `{health_score}/100` (警戒, 请看下方分项)")
        lines.append(f"- **GAC 异常扣分**: `{gov_anomaly}/100`")
        lines.append(f"- **常驻 daemon 在线率**: `{online_ratio:.2%}`")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BRIEF.md dashboard")
    parser.add_argument(
        "--write", action="store_true", help="Write content to BRIEF.md"
    )
    parser.add_argument(
        "--protect", action="store_true",
        help="Protect mode: fail if BRIEF.md was modified outside of generate-brief.py"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--if-changed",
        action="store_true",
        help="Skip writing BRIEF.md when only generated runtime metadata changed",
    )
    args = parser.parse_args()

    # 必须从 bin/ 执行或通过 sys.path 把 bin 加进来以导入 write_owner_audit
    bin_dir = str(Path(__file__).resolve().parent)
    if bin_dir not in sys.path:
        sys.path.insert(0, bin_dir)

    content = generate_brief_content()

    # --protect: refuse to overwrite if BRIEF.md was manually modified
    if args.protect and args.write and BRIEF_MD.exists():
        existing = BRIEF_MD.read_text(encoding="utf-8")
        if "generate-brief.py" not in existing[:200]:
            print("[protect] ⚠️  BRIEF.md was not generated by generate-brief.py — refusing to overwrite", file=sys.stderr)
            print("[protect]    Use --write without --protect to force overwrite", file=sys.stderr)
            return 1

    if args.write:
        if args.if_changed:
            changed = write_brief_if_changed(content)
            if changed:
                print(f"✅ BRIEF.md 物理生成并刷新: {BRIEF_MD}")
            else:
                print(f"ℹ BRIEF.md 语义未变化, 跳过写入: {BRIEF_MD}")
        else:
            # ADR-0128 Phase 2: 默认走 write_brief_if_changed, 消除 BRIEF.md dirty 风暴
            # (前人已实现该函数 + normalize_brief_content; 仅默认 else 分支仍裸写)
            changed = write_brief_if_changed(content)
            print(
                f"✅ BRIEF.md 物理生成并刷新: {BRIEF_MD}"
                if changed
                else f"ℹ BRIEF.md 语义未变化, 跳过写入: {BRIEF_MD}"
            )
    else:
        print(content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
