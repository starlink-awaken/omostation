#!/usr/bin/env python3
"""async-audit.py — 异步任务统一抓手（盘点/对账/健康）

问题 (2026-07-03): 五个调度平面并存（crontab / LaunchAgents / Claude Scheduled /
.omo/cron 源文件 / 自制 cron-service），无统一视图、源与安装脱节、日志散落、
失败无告警（今晨 cron 瘫痪一天无人知）。

抓手 = 注册表 SSOT + 本审计器：
  注册表: @驾驶舱/_control/async-tasks.yaml（新增任务必须先登记——单入口原则）
  python3 async-audit.py --bootstrap  # 从实况生成注册表草稿（首次/补漏用）
  python3 async-audit.py              # 对账: 孤儿(实况有注册无)/缺失(注册有实况无), 漂移 exit 1
  python3 async-audit.py --status     # 健康表: 各任务日志最后活动时间

仅在 host 运行（需读 crontab/launchctl）。v1.0 | 2026-07-03
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
WS_ROOT = HOME / "Workspace"
REGISTRY = DOCS_ROOT / "@驾驶舱/_control/async-tasks.yaml"
LAUNCH_DIR = HOME / "Library/LaunchAgents"
CLAUDE_SCHED = DOCS_ROOT / "Claude/Scheduled"
OMO_CRON_SRC = WS_ROOT / ".omo/cron"

IGNORE_LAUNCHD = ("com.macpaw.", "homebrew.mxcl.")  # 第三方自管, 只展示不对账


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return ""


def scan_live() -> dict[str, dict]:
    """实况扫描 → {task_key: {plane, detail, running}}"""
    live: dict[str, dict] = {}
    # 1. crontab
    for line in sh(["crontab", "-l"]).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+(.*)$", line)
        if m:
            sched, cmd = m.groups()
            # 任务指纹: 优先取脚本文件名 (.py/.sh), 其次特征词, 兜底命令前缀
            script = re.search(r"([\w.\-]+\.(?:py|sh))", cmd)
            if script:
                name = script.group(1)
            elif "kos ingest" in cmd:
                name = "kos-weekly-ingest"
            else:
                name = re.sub(r"\W+", "-", cmd[:24]).strip("-")
            key = f"cron:{name}"
            n = 2
            while key in live:  # 同脚本多条目 (不同时刻) 编号区分
                key = f"cron:{name}#{n}"
                n += 1
            live[key] = {"plane": "crontab", "detail": f"{sched} · {cmd[:80]}", "running": True}
    # 2. LaunchAgents
    loaded = sh(["launchctl", "list"])
    for p in sorted(LAUNCH_DIR.glob("*.plist")):
        label = p.stem
        live[f"launchd:{label}"] = {
            "plane": "launchd", "detail": str(p),
            "running": label in loaded,
            "thirdparty": label.startswith(IGNORE_LAUNCHD),
        }
    # 3. Claude Scheduled
    if CLAUDE_SCHED.is_dir():
        for d in sorted(CLAUDE_SCHED.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                live[f"claude:{d.name}"] = {"plane": "claude-scheduled", "detail": str(d), "running": True}
    # 4. .omo/cron 源文件（应与 crontab 对应, 无对应即孤儿源）
    if OMO_CRON_SRC.is_dir():
        for f in sorted(OMO_CRON_SRC.glob("*crontab*")):
            live[f"cronsrc:{f.name}"] = {"plane": "cron-source", "detail": str(f), "running": None}
    # 5. runtime cron-service (L1 正规调度器, SQLite 任务库 · 2026-07-03 纳入)
    cron_db = HOME / ".cron-service/cron.db"
    if cron_db.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(f"file:{cron_db}?mode=ro", uri=True)
            for jid, name, sched, script in conn.execute("SELECT id,name,schedule,script FROM jobs"):
                key = re.sub(r"\W+", "-", name.lower()).strip("-")
                live[f"cronsvc:{key}"] = {"plane": "cron-service",
                                          "detail": f"{sched} · {script}", "running": True}
            conn.close()
        except Exception as e:  # noqa: BLE001
            live["cronsvc:_error"] = {"plane": "cron-service", "detail": f"读取失败 {e}", "running": False}
    return live


def load_registry() -> dict[str, dict]:
    if not REGISTRY.exists():
        return {}
    out, cur = {}, None
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^  ([a-z]+:[^:]+):\s*$", line)
        if m:
            cur = m.group(1)
            out[cur] = {}
        elif cur and (m2 := re.match(r"^    (\w+):\s*(.+)$", line)):
            out[cur][m2.group(1)] = m2.group(2).strip().strip('"')
    return out


def bootstrap(live: dict) -> str:
    lines = ["# async-tasks.yaml — 异步任务注册表 SSOT",
             "# 公约: 新增任何 cron/launchd/Claude 定时任务前, 先在此登记 (owner/目的必填)",
             "# 对账: python3 @公共/_runtime/async-audit.py (孤儿/缺失 exit 1)",
             f"# bootstrap: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
             "tasks:"]
    for key, v in sorted(live.items()):
        lines += [f"  {key}:",
                  f"    plane: {v['plane']}",
                  f"    detail: \"{v['detail'][:100]}\"",
                  "    owner: 待认领",
                  "    purpose: 待补",
                  "    log: 待补"]
    return "\n".join(lines) + "\n"


def _period_seconds(sched: str) -> int:
    """调度表达式 → 预期最大间隔 (粗粒度, 供活性阈值)."""
    s = sched.strip().lower()
    if m := re.match(r"every\s+(\d+)m", s):
        return int(m.group(1)) * 60
    if m := re.match(r"every\s+(\d+)h", s):
        return int(m.group(1)) * 3600
    parts = s.split()
    if len(parts) == 5:
        minute, hour, dom, _mon, dow = parts
        if minute.startswith("*/"):
            return int(minute[2:]) * 60
        if hour.startswith("*/"):
            return int(hour[2:]) * 3600
        if dow not in ("*", "?"):
            return 7 * 86400
        if dom not in ("*", "?"):
            return 31 * 86400
        return 86400
    return 86400


def _cron_api(path: str = "/health") -> dict | None:
    """调 cron-service HTTP API，失败返回 None."""
    import json, urllib.request
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:7450{path}", timeout=5)
        return json.loads(resp.read().decode())
    except Exception:
        return None


def health() -> int:
    """活性监控: 任务不只存在, 还要活着."""
    from datetime import datetime as dt
    now = datetime.now(timezone.utc)
    issues, ok_n = [], 0
    # 1. cron-service: 走 HTTP API，不再直读 SQLite（schema 与代码可能不一致）
    api = _cron_api()
    if api is None:
        issues.append("cron-service HTTP API 不可达 (127.0.0.1:7450) — 进程可能未运行")
    elif not api.get("scheduler_running"):
        issues.append("cron-service scheduler 未运行")
    else:
        health = api.get("jobs", {})
        with_errors = health.get("with_errors", 0)
        total = health.get("total", 0)
        enabled = health.get("enabled", 0)
        # API 聚合数据可能包含 disabled job 的 error，降级查 DB 校准
        if with_errors:
            real_enabled_errors = 0
            cron_db = HOME / ".cron-service/cron.db"
            if cron_db.exists():
                import sqlite3
                try:
                    conn = sqlite3.connect(f"file:{cron_db}?mode=ro", uri=True)
                    cur = conn.execute(
                        "SELECT name FROM jobs WHERE enabled=1 AND last_status IS NOT NULL AND last_status != 'ok'"
                    )
                    real_enabled_errors = len(cur.fetchall())
                    conn.close()
                except Exception:
                    real_enabled_errors = with_errors  # 降级用 API 值
            else:
                real_enabled_errors = with_errors
        else:
            real_enabled_errors = 0
        ok_n += enabled - real_enabled_errors
        if real_enabled_errors:
            issues.append(f"cron-service: {real_enabled_errors}/{enabled} enabled jobs 状态为 error")
    # 2. crontab(l4-governance): 日志 26h 内必有写入 (session-brief 每日保底)
    gov_log = DOCS_ROOT / "@驾驶舱/_generated/governance-cron.log"
    if gov_log.exists() and (now.timestamp() - gov_log.stat().st_mtime) < 26 * 3600:
        ok_n += 1
    else:
        issues.append("crontab:l4-governance 日志 26h 无写入 — cron 疑似瘫痪 (查 TCC/crontab -l)")
    # 3. launchd 非第三方: 装载即健康 (常驻由 launchd 自拉)
    loaded = sh(["launchctl", "list"])
    for p in LAUNCH_DIR.glob("*.plist"):
        if p.stem.startswith(IGNORE_LAUNCHD):
            continue
        if p.stem in loaded:
            ok_n += 1
        elif p.stem != "com.agora.serve":  # 已知按需项
            issues.append(f"launchd:{p.stem} 未装载")
    # 4. Claude 定时: 心跳文件 (约定: 任务 prompt 末尾 touch heartbeats/<任务名>)
    hb_dir = DOCS_ROOT / "@驾驶舱/_generated/heartbeats"
    hb = [f for f in hb_dir.glob("*") if f.name.lower() != "readme.md"] if hb_dir.is_dir() else []
    hb_note = f"Claude 心跳 {len(hb)} 个已接入" if hb else "Claude 定时任务心跳未接入 (灰区, 见 heartbeats/README)"
    for f in hb:
        if now.timestamp() - f.stat().st_mtime > 8 * 86400:
            issues.append(f"claude:{f.name} 心跳超 8 天")
    for i in issues:
        print(f"  ❌ {i}")
    print(("✅ 任务活性正常" if not issues else f"🔴 {len(issues)} 项活性异常")
          + f" ({ok_n} 健康 · {hb_note})")
    return 0 if not issues else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--health", action="store_true")
    args = ap.parse_args()
    if not sh(["crontab", "-l"]).strip() and not LAUNCH_DIR.is_dir():
        print("⏭ 非 host 环境 (无 crontab/LaunchAgents), 跳过异步任务对账")
        return 0
    if args.health:
        return health()
    live = scan_live()

    if args.bootstrap:
        draft = REGISTRY.with_suffix(".yaml.draft")
        draft.write_text(bootstrap(live), encoding="utf-8")
        print(f"✅ 注册表草稿 → {draft} （补齐 owner/purpose 后改名生效）")
        return 0

    if args.status:
        print(f"{'任务':<44} {'平面':<16} 运行")
        for k, v in sorted(live.items()):
            r = {True: "🟢", False: "⚪ 未装载", None: "—"}[v.get("running")]
            print(f"{k[:43]:<44} {v['plane']:<16} {r}")
        print(f"\n共 {len(live)} 项 · 注册表: {'存在' if REGISTRY.exists() else '❌ 未建 (先跑 --bootstrap)'}")
        return 0

    reg = load_registry()
    if not reg:
        print("❌ 注册表不存在或为空 — 先跑 --bootstrap 并补齐")
        return 2
    issues = []
    for k, v in live.items():
        if v.get("thirdparty"):
            continue
        if k not in reg:
            issues.append(f"孤儿(未登记): {k} ← {v['detail'][:70]}")
        elif reg[k].get("owner", "待认领") == "待认领":
            issues.append(f"未认领: {k}")
    for k in reg:
        if k not in live:
            issues.append(f"缺失(已登记未安装/已消失): {k}")
    for i in issues:
        print(f"  ❌ {i}")
    print(("✅ 异步任务对账一致" if not issues else f"🔴 {len(issues)} 项漂移") + f" ({len(live)} 实况 / {len(reg)} 登记)")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
