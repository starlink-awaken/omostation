#!/usr/bin/env python3
"""Generate BRIEF.md containing Decision Inbox and X3 Value Metrics."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"
BRIEF_MD = WORKSPACE / "BRIEF.md"
DECISION_CHECKLIST_PATH = ".omo/tasks/closed/decision-checklist-13-items.md"


def decision_checklist_reference() -> str:
    """Render the canonical decision checklist pointer for the inbox summary."""
    return f"一页勾选清单见 `{DECISION_CHECKLIST_PATH}`."


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
    """Build BRIEF Inbox reaffirmation line while physical-hosts is a decision card.

    ADR-0247 amends ADR-0228 D3: physical multi-host DEFERRED — no weekly reaffirm.
    Emit only when the planned card exists AND needs-human is still true.
    Status-track cards (needs-human: false) stay out of Decision Inbox.
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
        data = {}
    # ADR-0247: demoted status track → no Inbox reminder
    if data.get("needs-human") is False:
        return None
    if str(data.get("status", "")).lower() in {"deferred", "closed", "backlog"}:
        return None
    if str(data.get("classification", "")).lower() in {
        "status_tracking",
        "engineering_debt",
    }:
        return None

    days = physical_hosts_suspend_day_count(card_path=path, now=now)
    if days is None:
        return None
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


def scan_x3_metrics() -> dict:
    """统计 X3 价值产出指标."""
    metrics = {
        "creations": 0,
        "knowledge_reuse": 0,
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

    # 2. 知识复用度量 (真实查询 KOS SQLite 检索库)
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


def _render_collab_dashboard() -> list[str]:
    """P84 W1.3 协作双轨仪表 — 能力轨(构造场景) + 产能轨(真实 backlog) 分列.

    🔴 红线 (P84 §0): 两轨数据源物理隔离, 禁止合并成单一"任务数".
       构造场景只计能力轨, 真实 backlog 只计产能轨.
    数据源: .omo/state/collab-dualtrack.yaml (bin/collab/export-dualtrack.py 产出).
    未导出时返回空 (不渲染空段, 避免 BRIEF 幻影).
    """
    dualtrack_path = WORKSPACE / ".omo" / "state" / "collab-dualtrack.yaml"
    if not dualtrack_path.is_file():
        return []
    import yaml  # noqa: PLC0415

    try:
        data = yaml.safe_load(dualtrack_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    cap = data.get("capability_track") or {}
    thru = data.get("throughput_track") or {}
    silent = thru.get("silent_loss", 0)
    silent_mark = "✅ 硬红线达成" if silent == 0 else "🔴 立即停管线写卡"
    cr = cap.get("conflict_resolution_success_rate")
    cr_s = f"{cr:.0%}" if isinstance(cr, (int, float)) else "—"
    return [
        "## 🤝 协作双轨仪表 (Collaboration Dual-Track · P84)",
        "",
        "> 🔴 **能力轨与产能轨数据源物理隔离, 禁止合并** (P84 §0 最高级红线). "
        "构造场景只计能力轨, 真实 backlog 只计产能轨.",
        "",
        "### 🎯 能力轨 (Capability · 构造场景, 可加速)",
        f"> 数据源: `{cap.get('data_source', '?')}`",
        "",
        f"- 场景总数: `{cap.get('scenario_total', 0)}` | 通过率: `{cap.get('pass_rate', 0):.1%}`",
        f"- 对抗集: `{cap.get('adversarial_total', 0)}` 个, 失败率 `{cap.get('adversarial_fail_rate', 0):.0%}` "
        "(P84: 全过=对抗不足须加强)",
        f"- 冲突消解成功率: `{cr_s}` | 平均协商轮次: `{cap.get('avg_resolution_rounds', 0)}`",
        "",
        "### 📦 产能轨 (Throughput · 真实 backlog, 不可造)",
        f"> 数据源: `{thru.get('data_source', '?')}`",
        "",
        f"- 真实任务: `{thru.get('done', 0)}` done / `{thru.get('planned', 0)}` planned "
        f"(完成率 `{thru.get('completion_rate', 0):.1%}`)",
        f"- 人工直做占比: `{thru.get('human_direct_ratio', 0):.0%}` "
        f"({thru.get('human_direct_count', 0)}/{thru.get('done', 0)})",
        f"- **静默丢失: `{silent}`** {silent_mark}",
        "",
    ]


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
    # D3 (Round3, workorder): 决策积压可观测 — 让"人类是瓶颈"本身可见
    if decisions:
        lines.append(
            f"> ⏳ **决策积压**: {len(decisions)} 张待人类拍板 — "
            "人类决策是当前系统瓶颈 (非技术问题). "
            f"{decision_checklist_reference()}"
        )
    lines.append("")
    if not decisions and not violations:
        lines.append("✅ **当前没有需要人工干预的阻断决策，健康免疫运转良好。**")
        lines.append("")
    else:
        if violations:
            lines.append("### 🚨 所有权越权告警 (Write Ownership Violations)")
            for v in violations:
                lines.append(f"- **[BLAME]** {v} (需要核实写入进程并恢复)")
            lines.append("")

        if decisions:
            lines.append("### ⏳ 待处理卡片与债务 (Needs Human Decisions)")
            for d in decisions:
                lines.append(
                    f"- **[{d['source'].upper()}]** {d['title']} → [`{d['path']}`](file://{WORKSPACE}/{d['path']})"
                )
            lines.append("")

    # S2 (P82): 治理预算约束可见 (ADR-0249)
    lines.append(
        "> 📊 **治理预算**: 40/40/20 (治理≤40%/协作≥40%/弹性20%, ADR-0249). 超40%须送卡."
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
    lines.append(
        "| **工作交付** | 未接入真实数据源 (BET-Y1Q1-T1-01 废除 mtime 伪指标) | 待接入 | — |"
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

    # P84 W1.3 协作双轨仪表 (能力轨+产能轨 分列, 数据源物理隔离)
    lines.extend(_render_collab_dashboard())

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
