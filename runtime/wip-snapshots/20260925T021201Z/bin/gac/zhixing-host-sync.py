#!/usr/bin/env python3
"""织星驾驶舱（:43191）宿主文件 — 版本化、漂移检测与恢复.

问题（docs/DASHBOARDS.md §3.1，2026-09-17 实证）:
主入口 `:43191` 的部署目录 `~/.local/share/zhixing-dashboard/` **不在任何 git
仓库中**。多 agent 并发编辑同一 `template.html` / `refresh.py` / `live_server.py`
会**互相覆盖**:

  - 场景系统面板被另一 agent 的「metrics redesign」覆盖丢失（所有备份均无该代码）
  - 该次覆盖同时回退了已修好的 `ens[n.type]` bug
  - 一处语法错误直接使整个第二脚本失效 → `D is not defined` → 页面主功能损坏

既有 `zhixing-panel-sync.py` 已**版本化 panels**（`bin/panorama/assets/panels/`）
并幂等注入 —— 但**宿主文件本身未纳管**，而它正是被覆盖的那个。本工具补上:

| 子命令    | 作用 |
|----------|------|
| `capture` | 部署目录 → 仓库（把当前线上态版本化; 人工确认后用） |
| `status`  | 逐文件 sha 对比（仓库 vs 部署）+ 漂移汇总 |
| `check`   | 有漂移 → exit 1（供 cron/patrol/门禁调用）; 每次运行把结构化报告原子写入 `~/.local/share/zhixing-dashboard/host-drift-report.json`（launchd 下比翻 stderr 系统日志易查） |
| `restore` | 仓库 → 部署（默认 dry-run; `--force` 才写） |

**为什么捕获"注入后"的态**: panels 由 `zhixing-panel-sync.py ensure` 幂等注入
（有 marker 则跳过），`refresh.py` 亦补丁幂等。故线上稳定态 = 已注入/已补丁态，
捕获它则不产生伪漂移。

用法:
    python3 bin/gac/zhixing-host-sync.py status
    python3 bin/gac/zhixing-host-sync.py check          # 漂移 → exit 1; 报告: ~/.local/share/zhixing-dashboard/host-drift-report.json
    python3 bin/gac/zhixing-host-sync.py capture        # 线上 → 仓库
    python3 bin/gac/zhixing-host-sync.py restore --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = _ROOT / "bin" / "panorama" / "assets" / "host"
DASHBOARD_DIR = Path.home() / ".local" / "share" / "zhixing-dashboard"

# 纳管范围: 宿主模板 + 采集器。数据/产物 (index.html, current.json, caches) 不入仓。
# 映射: (部署目录中的文件名, 仓库资产的相对名)。
#
# 为什么 refresh.py 的仓库名带 .asset 后缀: script-registry / bin-quota 两个门禁
# 都把 `bin/**/*.py` 视为**脚本**(排除规则只认 bin/_* 目录)。而这是部署文件的
# 版本化副本 —— 是**资产不是脚本**, 注册成脚本会污染脚本治理面。用 .asset 后缀
# 既保持与同行 panels 资产相邻 (bin/panorama/assets/), 又不误纳入脚本治理。
HOST_FILES: tuple[tuple[str, str], ...] = (
    ("template.html", "template.html"),
    ("refresh.py", "refresh.py.asset"),
    ("live_server.py", "live_server.py.asset"),
    ("observatory_query.py", "observatory_query.py.asset"),
    ("panorama-collect-main.py", "panorama-collect-main.py.asset"),
)

# check() 每次运行把漂移结果结构化写入部署目录的此文件 (原子写), 供 launchd
# 巡检后判读 —— exit 1 时详情只在 stderr (进系统日志不便查阅), 报告永远新鲜。
REPORT_NAME = "host-drift-report.json"


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def status(dashboard_dir: Path | None = None, host_dir: Path | None = None) -> dict:
    dash = dashboard_dir or DASHBOARD_DIR
    host = host_dir or HOST_DIR
    files = []
    drifted = missing_repo = missing_deploy = 0
    for deploy_name, repo_name in HOST_FILES:
        repo, live = host / repo_name, dash / deploy_name
        name = deploy_name
        rs, ls = _sha(repo), _sha(live)
        if rs is None:
            state = "no_repo_copy"
            missing_repo += 1
        elif ls is None:
            state = "no_deploy_copy"
            missing_deploy += 1
        elif rs == ls:
            state = "in_sync"
        else:
            state = "drifted"
            drifted += 1
        files.append({"name": name, "state": state, "repo_sha": rs, "deploy_sha": ls,
                      "repo_bytes": _size(repo), "deploy_bytes": _size(live)})
    return {
        "dashboard_dir": str(dash),
        "host_dir": str(host),
        "files": files,
        "drifted": drifted,
        "missing_repo_copy": missing_repo,
        "missing_deploy_copy": missing_deploy,
        "ok": drifted == 0 and missing_repo == 0 and missing_deploy == 0,
    }


def capture(dashboard_dir: Path | None = None, host_dir: Path | None = None) -> dict:
    dash = dashboard_dir or DASHBOARD_DIR
    host = host_dir or HOST_DIR
    host.mkdir(parents=True, exist_ok=True)
    captured, skipped = [], []
    for deploy_name, repo_name in HOST_FILES:
        live = dash / deploy_name
        if not live.is_file():
            skipped.append({"name": deploy_name, "reason": "deploy_missing"})
            continue
        dest = host / repo_name
        if _sha(dest) == _sha(live):
            skipped.append({"name": deploy_name, "reason": "already_same"})
            continue
        shutil.copy2(live, dest)
        captured.append({"name": deploy_name, "bytes": _size(dest), "sha": _sha(dest)})
    return {"ok": True, "captured": captured, "skipped": skipped}


def restore(force: bool = False, dashboard_dir: Path | None = None,
            host_dir: Path | None = None) -> dict:
    dash = dashboard_dir or DASHBOARD_DIR
    host = host_dir or HOST_DIR
    if not host.is_dir():
        print(f"❌ 仓库无宿主副本: {host}")
        return {"ok": False, "reason": "no_repo_copy"}
    planned, missing = [], []
    for deploy_name, repo_name in HOST_FILES:
        repo = host / repo_name
        if not repo.is_file():
            missing.append(deploy_name)
            continue
        live = dash / deploy_name
        if _sha(repo) == _sha(live):
            continue
        planned.append(deploy_name)
        if force:
            if live.is_file():
                shutil.copy2(live, dash / (deploy_name + ".before-restore"))
            shutil.copy2(repo, live)
    if not force and planned:
        print(f"（dry-run）将恢复 {len(planned)} 个文件; 加 --force 执行: {', '.join(planned)}")
    elif force:
        print(f"✅ 已从仓库恢复 {len(planned)} 个文件 (原文件留 .before-restore)")
    else:
        print("ℹ️  无差异, 无需恢复")
    return {"ok": True, "dry_run": not force, "restored": planned, "missing_repo": missing}


def _write_drift_report(info: dict, dashboard_dir: Path) -> None:
    """把每次 check 的结果原子写入部署目录的 host-drift-report.json。

    launchd 下 stderr 进系统日志不便查阅，结构化 JSON 可由 dashboard 读取展示，
    也可被 grep/告警脚本消费。始终写入（含无漂移），以便观察"最近一次检测时间"。
    """
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ok": bool(info.get("ok")),
        "drifted": int(info.get("drifted", 0)),
        "missing_repo_copy": int(info.get("missing_repo_copy", 0)),
        "missing_deploy_copy": int(info.get("missing_deploy_copy", 0)),
        "files": [
            {
                "name": f["name"],
                "state": f["state"],
                "repo_sha": f.get("repo_sha"),
                "deploy_sha": f.get("deploy_sha"),
                "repo_bytes": int(f.get("repo_bytes") or 0),
                "deploy_bytes": int(f.get("deploy_bytes") or 0),
            }
            for f in info.get("files", [])
        ],
    }
    out = dashboard_dir / "host-drift-report.json"
    tmp = out.with_suffix(".json.tmp")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, out)
    except OSError as exc:
        # 报告写入失败绝不能阻断 check 的 exit 语义；仅 stderr 提示。
        print(f"⚠️  漂移报告写入失败 ({exc}); check 结论仍按文件对比",
              file=sys.stderr)


def check(dashboard_dir: Path | None = None, host_dir: Path | None = None) -> int:
    info = status(dashboard_dir, host_dir)
    dash = Path(info["dashboard_dir"])
    if not dash.is_dir():
        return 0  # 非本机 / 未部署 → 天然跳过
    # 始终写报告（含无漂移），让 dashboard/告警能读"最近一次检测"。
    _write_drift_report(info, dash)
    if info["missing_repo_copy"]:
        print("⚠️  织星宿主文件未版本化: "
              + ", ".join(f["name"] for f in info["files"] if f["state"] == "no_repo_copy"),
              file=sys.stderr)
        print("   版本化: python3 bin/gac/zhixing-host-sync.py capture", file=sys.stderr)
    drifted = [f for f in info["files"] if f["state"] == "drifted"]
    if drifted:
        print("🔴 织星宿主文件漂移 (部署目录被直接编辑, 有被并发覆盖丢失的风险):",
              file=sys.stderr)
        for f in drifted:
            print(f"   - {f['name']}: 仓库 {f['repo_sha']} ({f['repo_bytes']}B) "
                  f"≠ 部署 {f['deploy_sha']} ({f['deploy_bytes']}B)", file=sys.stderr)
        print("   有意变更 → capture (版本化); 意外覆盖 → restore (从仓库回滚)", file=sys.stderr)
    return 0 if info["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")
    for name, helptext in (("status", "仓库 vs 部署 漂移摘要"),
                           ("capture", "部署 → 仓库 (版本化)"),
                           ("check", "有漂移 → exit 1")):
        sub.add_parser(name, help=helptext)
    rp = sub.add_parser("restore", help="仓库 → 部署 (默认 dry-run)")
    rp.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    command = args.command or "status"

    if command == "capture":
        result = capture()
    elif command == "restore":
        result = restore(force=args.force)
    elif command == "check":
        return check()
    else:
        result = status()
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
