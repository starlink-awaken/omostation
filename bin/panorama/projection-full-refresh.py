#!/usr/bin/env python3
"""projection-full-refresh.py — 全量投影数据周期刷新 driver (BET-Y2Q4-T10-227)

T10-223 的 republisher 只续租约 (重打 generated_at/fresh_until, 保留 data_observed_at),
投影内容的观测龄期随时间单调增长。本 driver 维护持久专用洁净检出并周期执行全量发布:

  1. flock 防重入 (运行中第二次触发直接跳过);
  2. remote 卫生校验 (origin 必须以 starlink-awaken/omostation.git 结尾);
  3. git fetch + reset --hard origin/main + clean -fdx + 浅子模块对齐;
  4. 以该检出为 PANORAMA_CODE_ROOT 运行检出内 panorama-collect.py 全量发布
     (publisher 自带 workspace 身份 + deploy 身份双校验, 一字不改);
  5. 发布成功后 republisher 自动接续续期新 revision。

fail-closed: 任何步骤失败 → 退出非零 + JSON 行日志; 旧 revision 仍由 republisher 续期,
读端全程可用。锁文件置于 deploy 侧 revisions/ 内 (state root 顶层会触发读端 CODE_DRIFT)。
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEPLOY_DIR = Path(
    os.environ.get("ZHIXING_DASHBOARD_STATE_ROOT", "~/.local/share/zhixing-dashboard")
).expanduser()
CHECKOUT = Path(
    os.environ.get("OMOSTATION_PUBLISHER_CHECKOUT", "~/.local/opt/omostation-publisher")
).expanduser()
LOCK_PATH = DEPLOY_DIR / "revisions" / ".fullrefresh.lock"
LOG_PATH = Path("~/.local/log/projection-fullrefresh.log").expanduser()
EXPECTED_ORIGIN_SUFFIX = "starlink-awaken/omostation.git"
CLONE_URL = "https://github.com/starlink-awaken/omostation.git"
PUBLISHER_TIMEOUT_SEC = 3600  # 全量采集典型 5~14min, 留足裕量
# event_ledger 是运行时文件（不在检出内）—— publisher 检出每轮 clean -fdx，那份按构造不存在。
# 根只能在调用时刻解析：import 时冻结会把 ledger 钉在一次性的 publisher 克隆上 (ADR-0456 B4b 前置, T10-247)。
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import canonical_root, state_root  # noqa: E402


def ledger_db_path() -> Path:
    """事件 ledger 的 DB 路径 (三行裁决, spec §2)。

    ① OMO_EVENT_LEDGER_DB 原样; ② 声明了 profile → state 根; ③ 都没声明 → canonical 检出。
    ③ 不是 code_root(): 本 driver 常驻执行位置是被 clean -fdx 的 publisher 克隆。
    canonical_root() 定位不到时抛 RuntimeError, 由调用方转成 fail-closed 的 JSON 日志行。
    """
    env = os.environ.get("OMO_EVENT_LEDGER_DB")
    if env:
        return Path(env).expanduser()
    if os.environ.get("OMOSTATION_STATE_ROOT"):
        return state_root() / "runtime" / "omo" / "event-ledger.sqlite3"
    return canonical_root() / "runtime" / "omo" / "event-ledger.sqlite3"


def log(event: str, **kw) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **kw}
    line = json.dumps(rec, ensure_ascii=False)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, timeout=timeout,
        text=True, capture_output=True,
    )


def fail(kind: str, **kw) -> int:
    # kind 而非 step: 调用方会传 step=<子步名> 关键字, 同名会 TypeError 掩盖真实错误
    log("failed", step=kind, **kw)
    return 1


def clear_stale_git_lock(checkout: Path, *, max_age_s: float = 600.0) -> None:
    """git 的 index.lock 是秒级短锁; 龄超限且无进程持有 → 必是 crash 残留, 清掉再对齐。
    2026-10-10 14:58 一枚 0 字节锁卡死投影链 43h (每 30min reset 撞锁), 加这道自愈。"""
    lock = checkout / ".git" / "index.lock"
    if not lock.exists():
        return
    age_s = time.time() - lock.stat().st_mtime
    if age_s <= max_age_s:
        return  # 可能属于活 git, 不误杀
    r = subprocess.run(["/usr/sbin/lsof", "--", str(lock)],
                       capture_output=True, text=True)
    if r.stdout.strip():
        log("stale_lock_held", age_s=round(age_s),
            holder=r.stdout.strip().splitlines()[-1][:120])
        return  # 有进程持有 (如长跑 gc), 留给它
    lock.unlink()
    log("stale_lock_cleared", age_s=round(age_s))


def main() -> int:
    # 0) 防重入锁
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lockf:
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("skip_already_running")
            return 0

        # 1) 定位 ledger 根 —— fail-closed: 定位不到就退出, 别跑完同步才发现
        try:
            ledger_db = ledger_db_path()
        except RuntimeError as exc:
            return fail("ledger_root", error=str(exc)[:300])
        log("ledger_root_resolved", path=str(ledger_db))

        # 2) 确保专用检出存在
        if not (CHECKOUT / ".git").exists():
            CHECKOUT.parent.mkdir(parents=True, exist_ok=True)
            r = run(["git", "clone", "--depth", "200", CLONE_URL, str(CHECKOUT)], timeout=1800)
            if r.returncode != 0:
                return fail("clone", stderr=(r.stderr or "")[-500:])
            log("checkout_cloned", path=str(CHECKOUT))
        else:
            r = run(["git", "-C", str(CHECKOUT), "remote", "get-url", "origin"])
            url = (r.stdout or "").strip()
            if not url.endswith(EXPECTED_ORIGIN_SUFFIX):
                return fail("remote_hygiene", url=url, expected_suffix=EXPECTED_ORIGIN_SUFFIX)
            log("remote_hygiene_ok", url=url)

        # 2) 清 crash 残留的 stale git 锁, 再对齐 origin/main (检出内无在制工作, clean -fdx 安全)
        clear_stale_git_lock(CHECKOUT)
        steps = [
            (["git", "fetch", "origin"], 1800),
            (["git", "reset", "--hard", "origin/main"], 300),
            (["git", "clean", "-fdx"], 600),
            (["git", "submodule", "sync", "--recursive"], 300),
            (["git", "submodule", "update", "--init", "--depth", "1"], 3600),
        ]
        for cmd, timeout in steps:
            r = run(cmd, cwd=CHECKOUT, timeout=timeout)
            if r.returncode != 0:
                return fail("sync_step", sub=cmd[1], stderr=(r.stderr or "")[-500:])
        head = run(["git", "rev-parse", "HEAD"], cwd=CHECKOUT).stdout.strip()
        log("checkout_synced", head=head)

        # 3) 全量发布 (用检出内 publisher, 与 origin/main 同步演进)
        env = dict(os.environ)
        env["PANORAMA_ROOT"] = str(CHECKOUT)
        env["PANORAMA_CODE_ROOT"] = str(CHECKOUT)
        env["ZHIXING_DASHBOARD_STATE_ROOT"] = str(DEPLOY_DIR)
        env["OMO_EVENT_LEDGER_DB"] = str(ledger_db)
        env["ZHIXING_DASHBOARD_CODE_ROOT"] = str(DEPLOY_DIR)
        r = subprocess.run(
            [sys.executable, "-B", str(CHECKOUT / "bin/panorama/panorama-collect.py")],
            cwd=str(CHECKOUT), env=env, text=True, capture_output=True,
            timeout=PUBLISHER_TIMEOUT_SEC,
        )
        if r.returncode != 0:
            return fail(
                "publish", rc=r.returncode,
                stderr=(r.stderr or "")[-800:], stdout_tail=(r.stdout or "")[-800:],
            )
        log("publish_ok", stdout_tail=(r.stdout or "")[-500:])
        return 0


if __name__ == "__main__":
    sys.exit(main())
