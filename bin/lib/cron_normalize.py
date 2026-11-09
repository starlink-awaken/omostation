r"""crontab 平面归一化的唯一实现 —— 登记面与安装态比对的公共口径.

为什么抽出来 (2026-11-07): `bin/scheduler-compile.py` 与
`bin/ops/install-cron-plane.py` 各自维护一份归一化, 两边的 docstring 都写着
「与对方同口径」, 但**没有任何门禁盯着** —— 于是静默漂移了两次:

1. `[:120]` 截断: scheduler-compile 按 BET-Y2Q4-T10-291 整行化, 安装器漏改,
   于是「前 120 字符相同、之后不同」的用户外部行会被误认领, 安装时**被删掉**
   (PR #5106 修)。
2. 解释器归一化的**范围**: 安装器是全局替换, 正则前缀 `\S*/` 会跨越 shell
   元字符, 把 `&&/opt/homebrew/bin/python3.13` 连 `&&` 一起吃掉; scheduler-compile
   按边界分段, 运算符保留 (本 PR 并轨)。
3. 末段 off-by-one: 两份实现都只处理到最后一个边界为止, 把 `cmd[last:]` 原样
   追加 ⇒ 行尾的解释器永远不被归一化, 登记面 `&& python3` vs 安装态
   `&& /opt/homebrew/bin/python3.13` 会报**假 drift** (本 PR 修)。

判据: 两个脚本的 `--dry-run` / `--check` / `--status` 输出必须逐字节相同;
新增用例钉住三种漂移形状, 而不只是钉当前实现.
"""

from __future__ import annotations

import re
from pathlib import Path

INTERPRETER_RE = re.compile(r"(?:\S*/)?python3(?:\.\d+)?(?=[\s]|$)")
INTERPRETER_BOUNDARY = re.compile(r"(?<=[\s;&|])")


def normalize_interpreter(cmd: str) -> str:
    r"""把解释器写法归一化成裸 `python3`, 使声明与安装态可比.

    注册表声明用 `python3 …`, 而安装态可能写成 `/opt/homebrew/bin/python3.13 …`
    (cron 环境里裸 `python3` 解析到 Xcode 的 3.9, 缺 `datetime.UTC`, 2026-10-22
    有 4 条 cron 因此连续失败数周). 两者语义相同, 不该算 drift.

    按**边界** (`空白` / `;` / `&` / `|`) 切段后逐段替换, 而不是全局替换:
    全局替换的正则前缀 `\S*/` 会跨越 shell 元字符, 把 `&&/opt/homebrew/bin/python3.13`
    整个吃成 `python3` (连 `&&` 一起没了); 分段后同样的输入得到 `&&python3`,
    运算符保留。注意分段**不**能阻止参数被误伤 —— `--flag=python3.13` 一样会被
    归一化, 这是该正则的固有边界, 别在 docstring 里承诺它挡参数.

    **末段也要归一化**: 边界之后的那一段同样是命令起始 (如 `&& python3.13`)。
    旧实现在循环里只处理到最后一个边界为止, 把 `cmd[last:]` 原样追加 ⇒ 行尾
    的解释器永远不被归一化: 登记面写 `&& python3` 而安装态写
    `&& /opt/homebrew/bin/python3.13` 时会报**假 drift** —— 正是本函数存在的
    目的。`tests/test_scheduler_compile.py` 的本地副本同形, 已一并去掉.
    """
    out, last = [], 0
    for boundary in INTERPRETER_BOUNDARY.finditer(cmd):
        seg = cmd[last:boundary.end()]
        out.append(INTERPRETER_RE.sub("python3", seg))
        last = boundary.end()
    out.append(INTERPRETER_RE.sub("python3", cmd[last:]))
    return "".join(out)


def expand_workspace(cmd: str) -> str:
    """把 registry 里的 `$HOME/Workspace` 写法展开成绝对路径.

    **cron 会通过 `/bin/sh -c` 执行命令, `$HOME` 会被 shell 展开** —— 实测已装面
    有 4 条行带着字面 `$HOME/Project/...` 且日志显示它们每次运行都成功
    (sched-health.log / kems-daily.log / daily-readings.log 当天仍在写)。

    所以展开不是「为了让作业能跑」, 而是为了让**登记面与安装面的比较口径一致**:
    不展开时 registry 的 `$HOME/Workspace` 与已装面的绝对路径对不上, check_drift
    会报 drift (PR #5138 之前 --diff 因此把 23 条 `$HOME` 拼法的作业同时报成
    removed 与 added)。

    根从 `Path.home()` 派生, 不写字面量: 写死本机用户目录会让**换机后**登记面
    全部指向不存在的路径 ⇒ check_drift 永久 drift, --diff 的判据随之失真.

    (此前 docstring 写「crontab 不走 shell 的变量展开」—— 那是**事实错误**,
    已按上面的实测订正。)
    """
    home = str(Path.home())
    return cmd.replace('"$HOME/Workspace"', f"{home}/Workspace").replace(
        "$HOME/Workspace", f"{home}/Workspace"
    )


def normalize_installed_line(s: str) -> str:
    """把一条已装 crontab 行折成规范形, 使登记面与安装态可比.

    `harness-cron.sh` 特例: 登记面把同一作业登记了两次 (`l4-harness-6h` 与
    `l4-harness-6h-active`), 已装面也因此有两行 —— 不折叠的话重复登记会被
    报成 drift/orphan. 根从 `Path.home()` 派生, 不写字面量 (换机后仍可比).
    """
    if "harness-cron.sh" in s:
        return (
            "0 */6 * * * cd "
            f"{Path.home()}/Workspace && bash projects/l4-kernel/scripts/"
            "harness-cron.sh >> runtime/cron/l4-harness-cron.log 2>&1"
        )
    return s


def comparison_key(line: str) -> str:
    """一行 crontab 的比较键 (归一化整行).

    不得截断: 截断会把「前 120 字符相同、之后不同」的两条行折成一个键 ——
    认领侧让用户自装的外部行被误认成登记面 (安装时删掉), 缺失侧让登记面里
    内容不同的两条塌成一条. 见 BET-Y2Q4-T10-291 与 PR #5106.
    """
    s = line.strip()
    if not s or s.startswith("#"):
        return ""
    return normalize_interpreter(normalize_installed_line(s))


def current_host() -> str:
    """本机主机名 —— cron 作业 `hosts` 维度的判据.

    可用 `CRON_HOST` 覆盖 (测试与 hostname 不合名的部署); 缺省取
    `socket.gethostname()` (实测 mbp / mini / studio 与债务条目里的机器名一致)。
    """
    import os
    import socket

    return os.environ.get("CRON_HOST") or socket.gethostname()


def host_scoped_jobs(jobs: list[dict]) -> list[dict]:
    """按 `hosts` 字段过滤登记条目: 缺省 (无 `hosts`) = 全部机器; 有 `hosts` = 仅列出的机器.

    CRON-REGISTRY-NO-HOST-SCOPE 的结构性修法: registry 是**跨机并集**, 而
    `check_drift` 的 `ok` 是**机器相对**的 —— 没有主机维度时, 单机专用条目在别的
    机器上永远算 drift (实证: `work-agent-respire-mbp-watchdog` 是 mini 专用, 在
    mbp 上 drift=1 ⇒ 本机健康门禁 A4 常红)。

    **为什么在归一化模块里**: `scheduler-compile` 与 `install-cron-plane` 各自
    编译登记面, 而后者此前没有主机维度 —— 安装器会把 mini 专用条目报成 `[MISSING]`
    并装上 (实测), 让 `check_drift` 的修复被安装侧抵消。同口径必须只有一份实现。
    """
    host = current_host()
    return [j for j in jobs if not j.get("hosts") or host in j["hosts"]]

