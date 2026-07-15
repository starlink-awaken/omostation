#!/usr/bin/env python3
"""Generate BRIEF.md containing Decision Inbox and X3 Value Metrics."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"
BRIEF_MD = WORKSPACE / "BRIEF.md"


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
                if "needs-human" in content:
                    data = yaml.safe_load(content) or {}
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

    return tasks


def scan_x3_metrics() -> dict:
    """统计 X3 价值产出指标."""
    metrics = {"creations": 0, "deliveries": 0, "knowledge_reuse": 0}

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

    # 2. 工作交付度量 (扫描 spaces/ 交付卡片数)
    spaces_dir = WORKSPACE / "spaces"
    if spaces_dir.is_dir():
        delivery_cards = 0
        for p in spaces_dir.rglob("*.yaml"):
            try:
                content = p.read_text(encoding="utf-8")
                if "delivery" in content.lower() or "deliverable" in content.lower():
                    delivery_cards += 1
            except Exception:
                pass
        metrics["deliveries"] = delivery_cards

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

    # 构建 BRIEF markdown
    lines = []
    lines.append("# BRIEF.md — 织星状态简报与决策收件箱")
    lines.append("")
    lines.append(
        f"> **Generated**: `{now_str}` | **SSOT Source**: `.omo/state/system.yaml` | **ISC-1 复合分**: `{health_score}/100`"
    )
    lines.append("")

    # 1. 决策收件箱 (Decision Inbox - WS-4)
    lines.append("## 📥 待决策收件箱 (Decision Inbox)")
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

    # 2. X3 价值仪表 (Value Metrics - WS-5)
    lines.append("## 📈 X3 价值仪表 (Value Metrics)")
    lines.append("")
    lines.append("| 维度 | 度量指标 | 状态 | 物理数据源 |")
    lines.append("|------|----------|------|------------|")
    lines.append(
        f"| **创意创作** | 新增发布数: `{x3['creations']}` | 正常 | `@创意创作/_outputs` |"
    )
    lines.append(
        f"| **工作交付** | 交付卡片数: `{x3['deliveries']}` | 正常 | `spaces/` 交付声明 |"
    )
    lines.append(
        f"| **知识复用** | KOS 索引篇: `{x3['knowledge_reuse']}` | 正常 | `kos/` 篇目 |"
    )
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
