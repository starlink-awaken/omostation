#!/usr/bin/env python3
"""从调度登记源安装 crontab 平面 (registry.yaml 是 SSOT, ADR-A / ADR-0119 / ADR-0121)。

**为什么需要这个脚本**: `scheduler-compile.py --generate crontab` 只产出**内容**, 没有把
内容**装到**本机 crontab 的动作 ⇒ 登记面与安装面各走各的。两机实测 (2026-11-03):
  · mini 装 43 条 (编译产物全覆盖)
  · mbp  只装 5 条 ⇒ `scheduler-compile.py --check` 报 drift 41
本脚本补上这一步: 编译 → 合并 → 写入, 幂等。

**安装语义 (与 install-maturity-cron.sh / install-resident-cron.sh 一致)**:
  · 保留本机 crontab 里**不属于本仓登记面**的行 (用户自装的外部工具,
    如 clash-*/fleet-*/bwg-*) —— 它们在 registry 的 known_orphans 里登记,
    但**不由本脚本管理**。
  · 替换掉「登记面里声明、但本机内容不同」的行 ⇒ 装完与登记逐字一致。
  · 幂等: 重复执行结果不变。

**为什么 mbp 需要它**: mbp 的 crontab 长期只装了 5 条, 其余 38 条登记面声明的
作业从未落到本机 ⇒ 那些巡检在 mbp 上根本没跑。历史归因写的是「mbp 的 crontab 写入在
系统层失败 (需 sudo)」, 但 2026-09-28 已更正为「crontab 现已可写」
(registry.yaml 的 zhixing-host-drift 条目 + 惰性注释探针实测), 且
/usr/bin/crontab 是 setuid root ⇒ 普通用户本就能写 /var/at/tabs。

用法:
    python3 bin/ops/install-cron-plane.py --install    # 安装/校准 (默认)
    python3 bin/ops/install-cron-plane.py --remove     # 移除本仓登记面 (留外部工具)
    python3 bin/ops/install-cron-plane.py --status     # 只看现状
    python3 bin/ops/install-cron-plane.py --dry-run    # 打印将写入的内容, 不写
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "lib"))
from cron_normalize import comparison_key as _key  # noqa: E402
from cron_normalize import expand_workspace as _expand_workspace  # noqa: E402
from cron_normalize import active_crontab_jobs as _active_crontab_jobs  # noqa: E402
from cron_normalize import resolve_python_command as _resolve_python_command  # noqa: E402

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "cron" / "registry.yaml"

def _load_raw() -> dict:
    import yaml

    if not REGISTRY.exists():
        return {}
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return docs[-1] if docs else {}



def _compiled_lines() -> list[str]:
    """登记面编译出的 crontab 行 (已按本机 `hosts` 作用域 + status/planes 过滤).

    过滤口径与 `scheduler-compile.compile_crontab` **同一份实现**
    (`cron_normalize.active_crontab_jobs`) —— 此前本函数自己过滤且漏掉主机维度,
    于是安装器把 mini 专用条目报成 `[MISSING]` 并装上, 让 check_drift 侧的修复被
    安装侧抵消 (CRON-REGISTRY-NO-HOST-SCOPE)。

    解释器解析同口径 (`cron_normalize.resolve_python_command`): 安装才是机器相关的
    一步, 登记面写裸 `python3` 而 cron 的 PATH 只有 `/usr/bin:/bin` ⇒ 解析到 Xcode
    的 3.9, `from datetime import UTC` 直接 ImportError (CRON-BARE-PYTHON3-PY39-IMPORT-DEATH)。
    与 `compile_crontab` 共用一份实现, 否则 `--generate` 与 `--install` 会装出两种内容。
    """
    raw = _load_raw()
    out = []
    for job in _active_crontab_jobs(raw.get("jobs", [])):
        cmd, _reason = _resolve_python_command(_expand_workspace(job.get("command", "")))
        out.append(f"{job.get('schedule', '')} {cmd}".strip())
    return out


def _current_text() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def _current_lines() -> list[str]:
    return _current_text().splitlines()


def _write_crontab(new: str) -> int:
    """把 new 写进本机 crontab。已一致则跳过; 写入失败时把内容打出来供手工应用。

    **已一致就跳过**: 无条件重写会让每次 --install 都触发 cron 重载 + crontab
    mtime 变动, 即使什么都没改。本机 `crontab(1)` 写入持续 EINTR 时, 这一条还能
    让「已对齐」的安装成功 (否则明明没事也会失败)。

    **失败要把内容打出来**: 只抛 CalledProcessError 的话, 调用者拿不到可以直接
    手工应用的内容 (实测本机 crontab 写入 EINTR 时就卡在这里)。
    """
    if new == _current_text():
        print("已对齐，无需写入")
        return 0
    result = subprocess.run(["crontab", "-"], input=new, text=True, capture_output=True)
    if result.returncode == 0:
        return 0
    err = (result.stderr or "").strip()
    print(f"❌ crontab 写入失败 (rc={result.returncode})", file=sys.stderr)
    if err:
        print(f"   {err}", file=sys.stderr)
    print("   把下面内容手工写入 crontab:", file=sys.stderr)
    print("   " + "-" * 60, file=sys.stderr)
    for line in new.splitlines():
        print(f"   {line}", file=sys.stderr)
    print("   " + "-" * 60, file=sys.stderr)
    return 1


def _is_managed(line: str, managed_keys: set[str]) -> bool:
    """该行是否属于本仓登记面 (⇒ 装的时候要替换它)。

    判据: 行的比较键与某条登记面条目相同 ⇒ 是登记面的行。
    登记面**没有**的 (用户的外部工具) ⇒ 保留不动。
    """
    key = _key(line)
    return bool(key) and key in managed_keys


def main() -> int:
    parser = argparse.ArgumentParser(description="从调度登记源安装 crontab 平面")
    parser.add_argument("--install", action="store_true", help="安装/校准 (默认)")
    parser.add_argument("--remove", action="store_true", help="移除本仓登记面的行")
    parser.add_argument("--status", action="store_true", help="只看现状")
    parser.add_argument("--dry-run", action="store_true", help="打印将写入的内容, 不写")
    args = parser.parse_args()

    compiled = _compiled_lines()
    managed_keys = {_key(line) for line in compiled}
    current = _current_text().splitlines()
    current_keys = {_key(line) for line in current}

    if args.status:
        present = [line for line in current if _key(line) in managed_keys]
        missing = [line for line in compiled if _key(line) not in current_keys]
        print(
            f"登记面 crontab 条目: {len(compiled)}  "
            f"本机已装: {len(present)}  缺失: {len(missing)}"
        )
        for line in missing:
            print(f"  [MISSING] {line[:150]}")
        return 0 if not missing else 1

    if args.remove:
        kept = [line for line in current if not _is_managed(line, managed_keys)]
        new = "\n".join(kept).rstrip() + "\n"
        if args.dry_run:
            print(new)
            return 0
        if _write_crontab(new) != 0:
            return 1
        print("已移除本仓登记面的 crontab 行 (外部工具行保留)")
        return 0

    # --install (默认): 保留非登记面的行, 去掉登记面里内容不同的旧行, 再追加登记面的行。
    kept = [line for line in current if not _is_managed(line, managed_keys)]
    new_lines = kept + compiled
    new = "\n".join(new_lines).rstrip() + "\n"
    if args.dry_run:
        print(new)
        return 0
    if _write_crontab(new) != 0:
        return 1
    print(
        f"已安装 {len(compiled)} 条登记面 crontab 条目 "
        f"(保留 {len(kept)} 行非登记面条目)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
