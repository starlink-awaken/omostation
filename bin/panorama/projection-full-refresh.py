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


def fail(step: str, **kw) -> int:
    log("failed", step=step, **kw)
    return 1


def main() -> int:
    # 0) 防重入锁
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lockf:
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("skip_already_running")
            return 0

        # 1) 确保专用检出存在
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

        # 2) 对齐 origin/main (检出内无在制工作, clean -fdx 安全)
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
                return fail("sync_step", step=cmd[1], stderr=(r.stderr or "")[-500:])
        head = run(["git", "rev-parse", "HEAD"], cwd=CHECKOUT).stdout.strip()
        log("checkout_synced", head=head)

        # 3) 全量发布 (用检出内 publisher, 与 origin/main 同步演进)
        env = dict(os.environ)
        env["PANORAMA_ROOT"] = str(CHECKOUT)
        env["PANORAMA_CODE_ROOT"] = str(CHECKOUT)
        env["ZHIXING_DASHBOARD_STATE_ROOT"] = str(DEPLOY_DIR)
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
