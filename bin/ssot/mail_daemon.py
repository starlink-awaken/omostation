#!/usr/bin/env python3
"""Mail Daemon — 工作域邮件感知+认知+规划 守护进程.

每30分钟: 读邮件 → LLM分类 → 任务提取 → 日报 → 高优任务生成草稿.
安全: 所有行动只生成草稿, 不自动发送.

Usage:
  python3 bin/ssot/mail_daemon.py --once
  python3 bin/ssot/mail_daemon.py --run --interval 1800
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _shared import ROOT, append_jsonl, utc_now
from doc_generator import generate_doc, save_draft
from mail_agent import classify_mail, extract_task, generate_briefing
from mail_reader import read_all

INBOX = Path.home() / "Documents" / "_inbox"
HEARTBEAT = ROOT / ".omo" / "state" / "mail-daemon.jsonl"
STABLE_JR = ROOT / "runtime" / "ssot-stable" / "journey-runner.py"
JOURNEY_TRIGGERED = ROOT / ".omo" / "state" / "mail-journey-triggered.json"
PID_FILE = ROOT / "runtime" / "mail-daemon" / "daemon.pid"
EVENTS_JSONL = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
COCKPIT_INBOX_TASKS = ROOT / "runtime" / "cockpit" / "inbox-tasks.json"

# 主题级黑名单 (2026-08-28 P1a: JetBrains 仓库通知刷屏占 91.9%, 分类前直接跳过 —
# 比 RULE_PRECLASSIFY 更省: 不分类不落库不占 briefing 名额, 让真任务浮出来)
SUBJECT_BLACKLIST = ("[JetBrains/",)


def _emit_signal_ingressed(mail: Any, cls: dict[str, Any], task: dict[str, Any], journey_res: dict[str, Any] | None) -> dict[str, Any]:
    """向全局事件总线发射标准 SignalIngressed 事件 (BET-Y2Q1-T4-02)."""
    event = {
        "event_type": "SignalIngressed",
        "topic": "mesh:signal:mail",
        "source": "apple_mail",
        "subject": getattr(mail, "subject", "")[:100],
        "sender": getattr(mail, "sender", "")[:100],
        "category": cls.get("category", "任务"),
        "task_type": task.get("task_type", "work_plan") if isinstance(task, dict) else "work_plan",
        "priority": cls.get("priority", "normal"),
        "task_summary": (task.get("summary") or getattr(mail, "subject", ""))[:200] if isinstance(task, dict) else "",
        "journey_triggered": bool(journey_res and journey_res.get("ok")),
        "ts": utc_now(),
    }
    append_jsonl(EVENTS_JSONL, event)
    return event


def _project_to_cockpit_inbox(mail: Any, cls: dict[str, Any], task: dict[str, Any], journey_res: dict[str, Any] | None) -> None:
    """将提炼出的待办与初稿原子投影到 Cockpit 统一待办池 (BET-Y2Q1-T4-02)."""
    try:
        data = json.loads(COCKPIT_INBOX_TASKS.read_text(encoding="utf-8")) if COCKPIT_INBOX_TASKS.exists() else {}
    except Exception:
        data = {}
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    key = getattr(mail, "subject", "")[:80]
    if any(isinstance(t, dict) and t.get("subject") == key for t in tasks):
        return

    import hashlib
    task_id = "mail-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    new_task = {
        "id": task_id,
        "source": "mail",
        "subject": key,
        "sender": getattr(mail, "sender", "")[:50],
        "category": cls.get("category", "任务"),
        "priority": cls.get("priority", "normal"),
        "status": "pending_review",
        "created_at": utc_now(),
        "task_detail": task if isinstance(task, dict) else {},
        "journey_status": journey_res.get("ok") if journey_res else None,
    }
    tasks.insert(0, new_task)
    data = {
        "schema_version": "cockpit-inbox-tasks/v1",
        "updated_at": utc_now(),
        "tasks": tasks[:100],
    }
    COCKPIT_INBOX_TASKS.parent.mkdir(parents=True, exist_ok=True)
    COCKPIT_INBOX_TASKS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_status() -> dict[str, Any]:
    """返回当前守护进程运行健康度诊断信息 (BET-Y2Q1-T4-02)."""
    import os
    is_running = False
    pid = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            is_running = True
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
            is_running = False

    last_heartbeat: dict[str, Any] | None = None
    if HEARTBEAT.exists():
        try:
            lines = [line.strip() for line in HEARTBEAT.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                last_heartbeat = json.loads(lines[-1])
        except Exception:
            pass

    pending_inbox = 0
    if COCKPIT_INBOX_TASKS.exists():
        try:
            data = json.loads(COCKPIT_INBOX_TASKS.read_text(encoding="utf-8"))
            pending_inbox = len(data.get("tasks", []))
        except Exception:
            pass

    return {
        "daemon": "mail_daemon",
        "running": is_running,
        "pid": pid if is_running else None,
        "pid_file": str(PID_FILE),
        "last_heartbeat": last_heartbeat,
        "pending_inbox_tasks": pending_inbox,
        "status": "healthy" if is_running else "stopped",
        "ts": utc_now(),
    }


def _blacklisted(subject: str) -> bool:
    subj = str(subject or "")
    return any(subj.startswith(p) or f" {p}" in subj or f"Re: {p}" in subj for p in SUBJECT_BLACKLIST)


def _trigger_journey_live(mail: Any, cls: dict) -> dict[str, Any] | None:
    """对任务邮件自动跑 journey --live (闭环最后一公里, 2026-08-26)。

    journey 七步全程草稿模式(HITL 挡发送), 自动跑安全; 人工只剩审草稿
    决定发不发。防重入: subject 已触发过即跳过 — 未读邮件不会消失,
    不去重会每 30min 重复产五草稿(_drafts 的 -1/-2/-3 堆积实锤)。
    """
    try:
        seen = json.loads(JOURNEY_TRIGGERED.read_text(encoding="utf-8")) if JOURNEY_TRIGGERED.exists() else {}
    except Exception:
        seen = {}
    key = (mail.subject or "")[:80]
    if key in seen:
        return None
    payload = json.dumps({"subject": key, "sender": (mail.sender or "")[:30]}, ensure_ascii=False)
    try:
        r = subprocess.run(
            [
                "python3", str(STABLE_JR), "--root", str(ROOT),
                "run", "--journey", "admin-notification-workflow",
                "--input", payload, "--live",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        ok = r.returncode == 0 and '"status": "completed"' in (r.stdout or "")
        rec = {"ts": utc_now(), "ok": ok}
        seen[key] = rec
        JOURNEY_TRIGGERED.parent.mkdir(parents=True, exist_ok=True)
        JOURNEY_TRIGGERED.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"subject": key, **rec}
    except Exception as exc:
        return {"subject": key, "error": str(exc)[:80]}


def run_cycle() -> dict[str, Any]:
    ts = utc_now()
    mails = read_all(limit=20, unread_only=True)
    if not mails:
        result = {"ts": ts, "mails": 0, "status": "no_unread"}
        append_jsonl(HEARTBEAT, result)
        return result

    classifications = []
    tasks = []
    skipped = 0
    for mail in mails:
        if _blacklisted(getattr(mail, "subject", "")):
            skipped += 1
            continue
        cls = classify_mail(mail)
        classifications.append(cls)
        if cls.get("category") == "任务":
            task = extract_task(mail, cls)
            if task:
                tasks.append((mail, cls, task))

    briefing = generate_briefing(mails, classifications)
    INBOX.mkdir(parents=True, exist_ok=True)
    briefing_path = INBOX / f"{ts[:10]}-mail-briefing.md"
    briefing_path.write_text(briefing, encoding="utf-8")

    drafts = 0
    for mail, cls, task in tasks:
        if cls.get("priority") == "high":
            template_map = {
                "转发通知": "forward_notice",
                "收集数据": "data_collection",
                "提交报告": "summary_report",
            }
            template = template_map.get(task.get("task_type", ""), "work_plan")
            content = generate_doc(
                template,
                {
                    "subject": mail.subject,
                    "sender": mail.sender,
                    "body": mail.body[:200],
                    "deadline": task.get("deadline", ""),
                    "task_detail": task,
                },
            )
            save_draft(template, content)
            drafts += 1

    # 自动触发 journey --live(闭环最后一公里): 任务到达 30min 内自动产
    # 五草稿。每轮最多 1 个(防 LLM 风暴, 7步全链约 3 分钟), 其余任务仍走
    # briefing 桥接命令人工触发; 已触发 subject 去重。
    journeys: list[dict[str, Any]] = []
    if tasks:
        j = _trigger_journey_live(tasks[0][0], tasks[0][1])
        if j:
            journeys.append(j)

    emitted_events = []
    for mail, cls, task in tasks:
        j_match = next((item for item in journeys if item.get("subject") == getattr(mail, "subject", "")[:80]), None)
        ev = _emit_signal_ingressed(mail, cls, task, j_match)
        emitted_events.append(ev)
        _project_to_cockpit_inbox(mail, cls, task, j_match)

    result = {
        "ts": ts,
        "mails": len(mails),
        "skipped_blacklist": skipped,
        "tasks": len(tasks),
        "drafts": drafts,
        "journeys": journeys,
        "events_emitted": len(emitted_events),
        "briefing": str(briefing_path),
        "status": "ok",
    }
    append_jsonl(HEARTBEAT, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--status", action="store_true", help="查询守护进程运行健康度诊断")
    parser.add_argument("--interval", type=int, default=1800)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        st = get_status()
        if args.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
        else:
            state_desc = "🟢 运行中" if st["running"] else "⚪ 已停止"
            print(f"Mail Daemon: {state_desc} (PID: {st['pid']})")
            if st.get("last_heartbeat"):
                hb = st["last_heartbeat"]
                print(f"  最后心跳: {hb.get('ts')} | 处理邮件: {hb.get('mails')} | 任务: {hb.get('tasks')} | 草稿: {hb.get('drafts')}")
            print(f"  Cockpit 待审待办: {st['pending_inbox_tasks']}")
        return 0

    if not args.run:
        result = run_cycle()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"📧 邮件处理 ({result['ts']}): {result['mails']}封 {result['tasks']}任务 {result['drafts']}草稿 事件:{result.get('events_emitted', 0)}")
        return 0

    import os
    import signal
    import time

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            os.kill(existing_pid, 0)
            print(f"❌ 守护进程已在运行中 (PID={existing_pid})", file=sys.stderr)
            return 1
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)

    my_pid = os.getpid()
    PID_FILE.write_text(str(my_pid), encoding="utf-8")

    def _cleanup_pid(*_args: Any) -> None:
        PID_FILE.unlink(missing_ok=True)
        print("\nMail Daemon 优雅退出，清理 PID 文件。", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _cleanup_pid)
    signal.signal(signal.SIGINT, _cleanup_pid)

    print(f"Mail Daemon 启动常驻守护 (PID={my_pid}, interval={args.interval}s)", flush=True)
    try:
        while True:
            result = run_cycle()
            print(
                f"  [{result['ts'][:19]}] mails={result['mails']} tasks={result['tasks']} drafts={result['drafts']}",
                flush=True,
            )
            time.sleep(args.interval)
    except Exception as exc:
        print(f"❌ 守护进程异常中断: {exc}", file=sys.stderr)
        _cleanup_pid()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
