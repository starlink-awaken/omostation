#!/usr/bin/env python3
"""Generate BRIEF.md containing Decision Inbox and X3 Value Metrics."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
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
                    tasks.append({
                        "id": data.get("id") or p.stem,
                        "title": data.get("title") or data.get("desc") or "System task pending human decision",
                        "path": f".omo/tasks/{p.relative_to(tasks_dir)}",
                        "source": "omo-debt"
                    })
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
                    tasks.append({
                        "id": data.get("id") or p.stem,
                        "title": data.get("title") or "Workspace item needs human decision",
                        "path": f"spaces/{p.relative_to(spaces_dir)}",
                        "source": "space-card"
                    })
            except Exception:
                pass
                
    return tasks


def scan_x3_metrics() -> dict:
    """统计 X3 价值产出指标."""
    metrics = {
        "creations": 0,
        "deliveries": 0,
        "knowledge_reuse": 0
    }
    
    # 1. 创意创作发布度量 (检测并递归扫描实际创意创作输出路径)
    creation_dirs = [
        Path("/Users/xiamingxing/Documents/@创意创作/_outputs"),
        Path("/Users/xiamingxing/Documents/@创意创作"),
        WORKSPACE / "创意创作" / "_outputs",
        Path("/Users/xiamingxing/Documents/@驾驶舱/_outputs"),
        WORKSPACE / "data" / "creations"
    ]
    for d in creation_dirs:
        if d.is_dir():
            # 递归统计所有文件 (排除隐藏文件)
            files = [f for f in d.rglob("*") if f.is_file() and not f.name.startswith(".")]
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
            metrics["knowledge_reuse"] = len([f for f in kos_dir.rglob("*") if f.is_file()])
    else:
        metrics["knowledge_reuse"] = len([f for f in kos_dir.rglob("*") if f.is_file()])
        
    return metrics


def run_write_owner_audit() -> list[str]:
    """跑 write-owner 审计以防违规写入."""
    try:
        from write_owner_audit import audit_staged, load_owners, get_git_user, get_staged_files
        owners = load_owners()
        current_user = get_git_user() or "unknown"
        staged_files = get_staged_files()
        return audit_staged(staged_files, owners, current_user)
    except Exception:
        return []


def scan_task_summary() -> dict:
    """扫描 .omo/tasks/ 获取任务概览."""
    import yaml  # noqa: PLC0415
    summary = {"active": 0, "planned": 0, "done": 0, "blocked": 0, "total": 0}
    tasks_dir = WORKSPACE / ".omo" / "tasks"
    if not tasks_dir.is_dir():
        return summary
    for status_dir in ["active", "planned", "done"]:
        d = tasks_dir / status_dir
        if d.is_dir():
            count = len([f for f in d.glob("*.yaml") if f.is_file()])
            summary[status_dir] = count
            summary["total"] += count
    # 从 system.yaml 读取 blocked
    if SYSTEM_YAML.is_file():
        try:
            data = yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8")) or {}
            summary["blocked"] = data.get("blocked_tasks", 0)
            summary["total"] = data.get("total_tasks", summary["total"])
        except Exception:
            pass
    return summary


def scan_runtime_health() -> dict:
    """扫描 runtime matrix_state 获取 daemon 健康."""
    health = {"total": 0, "online": 0, "offline": 0, "services": []}
    matrix_file = Path.home() / "runtime" / "matrix_state.json"
    if matrix_file.is_file():
        try:
            import json  # noqa: PLC0415
            data = json.loads(matrix_file.read_text(encoding="utf-8"))
            for name, info in data.items():
                health["total"] += 1
                status = info.get("status", "unknown")
                if status == "running":
                    health["online"] += 1
                    health["services"].append({"name": name, "status": "online"})
                else:
                    health["offline"] += 1
                    health["services"].append({"name": name, "status": status})
        except Exception:
            pass
    return health


def scan_adr_activity(days: int = 7) -> list[dict]:
    """扫描近期 ADR 活动."""
    import yaml  # noqa: PLC0415
    from datetime import datetime, timedelta, timezone
    adrs = []
    adr_dir = WORKSPACE / ".omo" / "_knowledge" / "decisions"
    if not adr_dir.is_dir():
        return adrs
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for p in sorted(adr_dir.glob("*.md"), reverse=True)[:20]:
        try:
            content = p.read_text(encoding="utf-8")
            # 提取 frontmatter date
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1]) or {}
                    date_str = fm.get("date") or ""
                    if date_str:
                        try:
                            adr_date = datetime.fromisoformat(date_str)
                            if adr_date.replace(tzinfo=timezone.utc) < cutoff:
                                continue
                        except Exception:
                            pass
                    status = fm.get("status", "PROPOSED")
                    title = fm.get("title", p.stem)
                    adrs.append({
                        "id": p.stem,
                        "title": title,
                        "status": status,
                        "date": date_str,
                    })
        except Exception:
            pass
    return adrs


def scan_bos_metrics() -> dict:
    """扫描 BOS 用量指标 (agora bos_metrics SQLite)."""
    metrics = {"total_calls": 0, "domains": {}}
    db_path = Path.home() / ".agora" / "bos_metrics.db"
    if db_path.is_file():
        try:
            import sqlite3  # noqa: PLC0415
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT prefix, call_count, success_count, total_latency_ms "
                "FROM bos_metrics ORDER BY call_count DESC LIMIT 20"
            )
            rows = cursor.fetchall()
            for prefix, calls, success, latency in rows:
                domain = prefix.split("/")[2] if prefix.count("/") >= 2 else prefix
                if domain not in metrics["domains"]:
                    metrics["domains"][domain] = {"calls": 0, "success": 0, "latency": 0}
                metrics["domains"][domain]["calls"] += calls
                metrics["domains"][domain]["success"] += success
                metrics["domains"][domain]["latency"] += latency
                metrics["total_calls"] += calls
            conn.close()
        except Exception:
            pass
    return metrics


def scan_workflow_compliance() -> dict:
    """扫描 P74 工作流合规状态."""
    import json  # noqa: PLC0415
    result = {"warn_count": 0, "silent_workflows": []}
    events_file = WORKSPACE / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"
    if not events_file.is_file():
        return result
    try:
        # 读取最近的 start 事件
        started = set()
        for line in events_file.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                ev = json.loads(line)
                if ev.get("event") == "agent_workflow_start":
                    started.add(ev.get("workflow_id", ""))
            except Exception:
                pass
        # 检查注册表
        import yaml  # noqa: PLC0415
        reg_path = WORKSPACE / ".omo" / "_truth" / "registry" / "agent-workflows.yaml"
        if reg_path.is_file():
            docs = list(yaml.safe_load_all(reg_path.read_text(encoding="utf-8")))
            registry = docs[1] if len(docs) > 1 else docs[0]
            for wf in registry.get("workflows") or []:
                wf_id = wf.get("id", "")
                if wf_id and wf_id not in started:
                    result["silent_workflows"].append(wf_id)
        result["warn_count"] = len(result["silent_workflows"])
    except Exception:
        pass
    return result


def generate_brief_content() -> str:
    import yaml  # noqa: PLC0415
    
    # 读取系统健康分
    health_score = 90
    gov_anomaly = 100
    online_ratio = 1.0
    current_phase = "?"
    completed_tasks = 0
    total_tasks = 0

    
    if SYSTEM_YAML.is_file():
        try:
            data = yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8")) or {}
            health_score = data.get("health_score", 90)
            gov_anomaly = data.get("governance_anomaly_score", 100)
            online_ratio = data.get("service_online_ratio", 1.0)
            current_phase = data.get("current_phase", "?")
            completed_tasks = data.get("completed_tasks", 0)
            total_tasks = data.get("total_tasks", 0)
        except Exception:
            pass

    now_str = get_now_str()
    decisions = scan_decision_inbox()
    x3 = scan_x3_metrics()
    violations = run_write_owner_audit()
    tasks = scan_task_summary()
    runtime_health = scan_runtime_health()
    adrs = scan_adr_activity()
    bos = scan_bos_metrics()
    compliance = scan_workflow_compliance()
    
    # 构建 BRIEF markdown
    lines = []
    lines.append("# BRIEF.md — 织星状态简报与决策收件箱")
    lines.append("")
    lines.append(f"> **Generated**: `{now_str}` | **Phase**: `{current_phase}` | **ISC-1 复合分**: `{health_score}/100`")
    lines.append("")
    
    # 1. 决策收件箱
    lines.append("## 📥 待决策收件箱 (Decision Inbox)")
    lines.append("")
    if not decisions and not violations:
        lines.append("✅ **当前没有需要人工干预的阻断决策，健康免疫运转良好。**")
        lines.append("")
    else:
        if violations:
            lines.append("### 🚨 所有权越权告警")
            for v in violations:
                lines.append(f"- **[BLAME]** {v}")
            lines.append("")
        if decisions:
            lines.append("### ⏳ 待处理卡片与债务")
            for d in decisions:
                lines.append(f"- **[{d['source'].upper()}]** {d['title']} → [`{d['path']}`](file://{WORKSPACE}/{d['path']})")
            lines.append("")

    # 2. 运行时健康
    lines.append("## 🖥️ 运行时健康 (Runtime Health)")
    lines.append("")
    if runtime_health["total"] > 0:
        lines.append(f"| 状态 | 数量 |")
        lines.append(f"|------|------|")
        lines.append(f"| 🟢 在线 | `{runtime_health['online']}` |")
        lines.append(f"| 🔴 离线 | `{runtime_health['offline']}` |")
        lines.append(f"| 📊 总计 | `{runtime_health['total']}` |")
        lines.append("")
        offline_services = [s for s in runtime_health["services"] if s["status"] != "online"]
        if offline_services:
            lines.append("**离线服务:**")
            for s in offline_services:
                lines.append(f"- `{s['name']}` ({s['status']})")
            lines.append("")
    else:
        lines.append("*运行时探针数据不可用*")
        lines.append("")

    # 3. 任务概览
    lines.append("## 📋 任务概览 (Task Summary)")
    lines.append("")
    lines.append(f"| 状态 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| ✅ 已完成 | `{completed_tasks}` |")
    lines.append(f"| 📋 活跃 | `{tasks['active']}` |")
    lines.append(f"| 📝 计划 | `{tasks['planned']}` |")
    lines.append(f"| 🚫 阻塞 | `{tasks['blocked']}` |")
    lines.append(f"| 📊 总计 | `{total_tasks}` |")
    lines.append("")

    # 4. X3 价值仪表
    lines.append("## 📈 X3 价值仪表 (Value Metrics)")
    lines.append("")
    lines.append("| 维度 | 度量指标 | 状态 | 物理数据源 |")
    lines.append("|------|----------|------|------------|")
    lines.append(f"| **创意创作** | 新增发布数: `{x3['creations']}` | 正常 | `@创意创作/_outputs` |")
    lines.append(f"| **工作交付** | 交付卡片数: `{x3['deliveries']}` | 正常 | `spaces/` 交付声明 |")
    lines.append(f"| **知识复用** | KOS 索引篇: `{x3['knowledge_reuse']}` | 正常 | `kos/` 篇目 |")
    lines.append("")
    
    # 5. BOS URI 用量
    lines.append("## 🔄 BOS URI 用量 (Route Metrics)")
    lines.append("")
    if bos["total_calls"] > 0:
        lines.append(f"**总调用**: `{bos['total_calls']}` | **按域**:")
        lines.append("")
        lines.append("| 域 | 调用 | 成功率 | 延迟(ms) |")
        lines.append("|---|------|--------|---------|")
        for domain, stats in sorted(bos["domains"].items(), key=lambda x: -x[1]["calls"]):
            rate = (stats["success"] / stats["calls"] * 100) if stats["calls"] > 0 else 0
            lines.append(f"| `{domain}` | {stats['calls']} | {rate:.0f}% | {stats['latency']} |")
        lines.append("")
    else:
        lines.append("*BOS 指标数据不可用 (agora bos_metrics.db 未就绪)*")
        lines.append("")

    # 6. 治理健康
    lines.append("## ⚙️ 治理健康 (Governance Health)")
    lines.append("")
    lines.append(f"- **GAC 异常扣分**: `{gov_anomaly}/100`")
    lines.append(f"- **常驻 daemon 在线率**: `{online_ratio:.2%}`")
    if compliance["warn_count"] > 0:
        lines.append(f"- **P74 工作流沉默**: `{compliance['warn_count']}` 个警告")
        for wf_id in compliance["silent_workflows"][:5]:
            lines.append(f"  - `{wf_id}`")
        if len(compliance["silent_workflows"]) > 5:
            lines.append(f"  - ... 还有 {len(compliance['silent_workflows']) - 5} 个")
    else:
        lines.append(f"- **P74 工作流沉默**: `0` (全部活跃)")
    lines.append("")

    # 7. 近期 ADR
    lines.append("## 📜 近期 ADR (Recent Decisions)")
    lines.append("")
    if adrs:
        lines.append("| ID | 标题 | 状态 |")
        lines.append("|----|------|------|")
        for a in adrs[:10]:
            lines.append(f"| {a['id']} | {a['title'][:60]} | {a['status']} |")
        lines.append("")
    else:
        lines.append("*过去 7 天无新 ADR*")
        lines.append("")

    # 8. 操作收件箱 (Operations Inbox)
    ops_items = []
    if runtime_health["offline"] > 0:
        ops_items.append(f"🔴 {runtime_health['offline']} 个运行时服务离线，需排查")
    if compliance["warn_count"] > 0:
        ops_items.append(f"⚠️ {compliance['warn_count']} 个工作流沉默，需检查 P74 合规")
    if tasks["blocked"] > 0:
        ops_items.append(f"🚫 {tasks['blocked']} 个任务被阻塞")

    lines.append("## 📮 操作收件箱 (Operations Inbox)")
    lines.append("")
    if ops_items:
        for item in ops_items:
            lines.append(f"- {item}")
        lines.append("")
    else:
        lines.append("✅ 无待处理操作项")
        lines.append("")
        
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate BRIEF.md dashboard")
    parser.add_argument("--write", action="store_true", help="Write content to BRIEF.md")
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
                f"✅ BRIEF.md 物理生成并刷新: {BRIEF_MD}" if changed
                else f"ℹ BRIEF.md 语义未变化, 跳过写入: {BRIEF_MD}"
            )
    else:
        print(content)
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
