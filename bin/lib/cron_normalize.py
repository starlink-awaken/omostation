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

import ast
import os
import re
import subprocess
import sys
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


# ---------------------------------------------------------------------------
# 解释器的宿主侧解析 (CRON-BARE-PYTHON3-PY39-IMPORT-DEATH 选项 ③)
#
# 登记面保持中性 (`python3 …`)，安装/生成时按**本机**换成可证可用的绝对路径。
# 三条不变量：
#   1. 判据是**执行探测**，不是正则。`from datetime import UTC` 出现在源码里
#      不等于该解释器会死（可能带 3.9 兼容分支），也不等于不会死（可能从本地
#      模块间接引入）。只查第三方依赖同样会误判 —— 2026-11-09 就据此把
#      `bin/ops/cli.py` 读成「3.9 可跑」，而它第 21 行的 UTC 在 3.9 下必死。
#   2. 探测**不执行目标脚本**：只 `find_spec` 顶层第三方模块名 + 版本下限。
#      import 目标脚本会跑它的模块级代码（网络/写盘），编译期不能碰。
#   3. 解不出可证安全的解释器就**原样返回**并给出原因。宁可留作业在既有失败
#      形态上（可登记、可见），也不要把它换成一个新的失败形态。
# ---------------------------------------------------------------------------

_PYTHON_INVOCATION_RE = re.compile(
    r"(?P<interp>(?:\S*/)?python3(?:\.\d+)?)[ \t]+"
    r"(?P<script>(?:[^\s'\"|;&]*/)?[^\s'\"|;&\[\]]+\.py)"
)
# 替换后的 token 必须仍能被 INTERPRETER_RE 折回裸 python3，否则 comparison_key
# 会把「登记面裸写 vs 安装态绝对路径」判成永久假 drift —— 本函数存在的目的
# 正是消除这类假 drift。
_FOLDABLE_INTERPRETER_RE = re.compile(r"/python3(?:\.\d+)?$")

# 版本下限的探针：datetime.UTC 只在 3.11+ 存在，等价于「跑得动本仓 cron 代码」。
_PROBE_SOURCE = (
    "import importlib.util, sys\n"
    "from datetime import UTC  # 3.11+ 下限\n"
    "missing = [m for m in sys.argv[1:] if importlib.util.find_spec(m) is None]\n"
    "sys.exit(1 if missing else 0)\n"
)

_probe_cache: dict[tuple[str, tuple[str, ...]], bool] = {}
_resolve_cache: dict[tuple, tuple[str, str | None]] = {}


def interpreter_candidates(repo_root: Path | str | None = None) -> list[str]:
    """本机候选解释器（绝对路径，按优先级）.

    仓内 `.venv` 排第一：它由项目自己维护，装齐了 cron 脚本的第三方依赖
    （实测 `bin/ops/cli.py` 需要的 `rich` 只有它和 3.9 的 site-packages 有，
    而 3.9 又缺 `datetime.UTC` ⇒ 只有 `.venv` 能同时满足）。
    只保留 basename 可被 `INTERPRETER_RE` 折回裸 `python3` 的候选 ——
    `.venv/bin/python`（basename 是 `python`）会被排除，用 `.venv/bin/python3`。
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    cands = [
        str(root / ".venv" / "bin" / "python3"),
        "/opt/homebrew/bin/python3.13",
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
    ]
    override = os.environ.get("CRON_INTERPRETER")
    if override:
        cands.insert(0, override)
    return [c for c in cands if _FOLDABLE_INTERPRETER_RE.search(c) and Path(c).exists()]


def third_party_imports(script: Path) -> list[str] | None:
    """脚本顶层 import 的第三方模块名；解析不了返回 None（= 不可判定）."""
    try:
        tree = ast.parse(script.read_text(errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return None
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return sorted(names - set(sys.stdlib_module_names) - {"__future__"})


def _interpreter_ok(candidate: str, script_dir: Path, deps: list[str]) -> bool:
    key = (candidate, tuple(deps))
    if key not in _probe_cache:
        env = dict(os.environ)
        # 仓内脚本靠同目录 import 兄弟模块（`_shared`、`doc_legs`），不加会误报缺包。
        env["PYTHONPATH"] = os.pathsep.join(
            [str(script_dir)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
        )
        try:
            r = subprocess.run(
                [candidate, "-c", _PROBE_SOURCE, *deps],
                capture_output=True, text=True, timeout=30, env=env, check=False,
            )
            _probe_cache[key] = r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            _probe_cache[key] = False
    return _probe_cache[key]


def resolve_python_command(
    cmd: str,
    *,
    candidates: list[str] | None = None,
    repo_root: Path | str | None = None,
) -> tuple[str, str | None]:
    """把 command 里的 `python3 <script>.py` 换成本机可证可用的解释器.

    返回 `(新 command, 原因)`；原因 `None` = 已替换成功或本就无需替换。
    只在**同时满足**版本下限与目标脚本顶层第三方依赖的候选里选，选不出就原样返回。
    """
    # 缓存键必须含候选集与根: 只按 cmd 缓存会让换了 candidates/CRON_INTERPRETER 的
    # 调用读到上一个宿主布局的结果。
    key = (cmd, None if candidates is None else tuple(candidates),
           None if repo_root is None else str(repo_root))
    if key in _resolve_cache:
        return _resolve_cache[key]
    result = _resolve_python_command_uncached(cmd, candidates=candidates, repo_root=repo_root)
    _resolve_cache[key] = result
    return result


def _repo_local_modules(root: Path) -> frozenset[str]:
    """仓内自有顶层模块名（脚本运行时靠自己的 sys.path.insert 找到）.

    为什么单独列: `omo` / `repo_root` / `capability_native_sources` 这类名字不在
    任何解释器的 site-packages 里, 直接 find_spec 会误报「缺包」⇒ 拒绝切换 ⇒ 作业
    留在 3.9 的 `ImportError: cannot import name 'UTC'` 上。仓内模块的可见性与
    **解释器无关**（脚本用 `Path(__file__)` 自己插 sys.path），所以只需判断它存在。
    """
    search_dirs = [root, root / "bin", root / "src", root / "lib"]
    search_dirs += sorted(p for p in (root / "bin").iterdir() if p.is_dir()) if (root / "bin").is_dir() else []
    search_dirs += sorted((root / "projects").glob("*/src")) if (root / "projects").is_dir() else []
    names: set[str] = set()
    for d in search_dirs:
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.suffix == ".py" and e.stem != "__init__":
                names.add(e.stem)
            elif e.is_dir() and (e / "__init__.py").is_file():
                names.add(e.name)
    return frozenset(names)


_repo_local_cache: dict[str, frozenset[str]] = {}


def _job_workspace(cmd: str, interp_start: int, fallback: Path | str | None) -> Path:
    """作业实际运行的工作区 = command 里 `cd <dir>` 的目标（可能是 `$HOME` 拼法）.

    解释器候选必须按**作业的工作区**取，而不是按编译副本自己的位置：worktree 里没有
    `.venv`，而作业永远 `cd $HOME/Workspace`（根有四类落点）。
    """
    cd = re.search(r"(?:^|[\s;&|])cd\s+(?P<dir>\"[^\"]+\"|[^\s;&|]+)", cmd[:interp_start])
    raw = cd.group("dir").strip('"') if cd else None
    if raw:
        p = Path(os.path.expanduser(os.path.expandvars(raw)))
        if p.is_dir():
            return p
    return Path(fallback) if fallback else Path(__file__).resolve().parents[2]


def pick_interpreter(
    cmd: str,
    *,
    candidates: list[str] | None = None,
    repo_root: Path | str | None = None,
) -> str | None:
    """本机跑动该 command 目标脚本会用的解释器；不可判定 (或没有 python 调用) → None.

    给 launchd 这类「解释器与命令分开存放」的平面用: 它需要的是解释器本身,
    而不是替换后的整条 command。
    """
    new, reason = resolve_python_command(cmd, candidates=candidates, repo_root=repo_root)
    if reason is not None:
        return None
    m = _PYTHON_INVOCATION_RE.search(new)
    return m.group("interp") if m else None


def _resolve_python_command_uncached(cmd, *, candidates, repo_root):
    m = _PYTHON_INVOCATION_RE.search(cmd)
    if not m:
        return cmd, None
    root = _job_workspace(cmd, m.start(), repo_root)
    token = m.group("script")
    script = Path(os.path.expanduser(os.path.expandvars(token)))
    if not script.is_absolute():
        script = root / script
    if not script.is_file():
        return cmd, f"target script not found: {script}"
    deps = third_party_imports(script)
    if deps is None:
        return cmd, f"unparseable target: {script}"
    key = str(root)
    if key not in _repo_local_cache:
        _repo_local_cache[key] = _repo_local_modules(root)
    external = [d for d in deps if d not in _repo_local_cache[key]]
    for cand in candidates if candidates is not None else interpreter_candidates(root):
        # 入选前复查可折回性: 调用方 (含 CRON_INTERPRETER) 传进不可折回的路径,
        # 会让 check_drift 把替换读成永久 drift ⇒ 宁可不换。
        if not _FOLDABLE_INTERPRETER_RE.search(cand):
            continue
        if _interpreter_ok(cand, script.parent, external):
            new = cmd[: m.start("interp")] + cand + cmd[m.end("interp") :]
            if new == cmd:
                return cmd, None
            return new, None
    tried = ", ".join(candidates if candidates is not None else interpreter_candidates(root)) or "(无候选)"
    return cmd, (
        f"no interpreter satisfies {script.name} (needs 3.11+ and {external or 'no third-party'}); "
        f"tried: {tried}"
    )


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


def active_plane_jobs(jobs: list[dict], plane: str) -> list[dict]:
    """本机该编译成指定平面的登记条目: `hosts` 作用域 + `status=active` + `planes` 含该平面.

    **单点实现** —— `scheduler-compile` 的各 `compile_*` 与
    `bin/ops/install-cron-plane.py` 的 `_compiled_lines` 共用。此前各方各自过滤,
    主机维度只在 crontab 侧生效, 于是 #5147 的修复被安装侧抵消 (mbp 上安装器仍把
    mini 专用条目报成 `[MISSING]` 并装上); `compile_launchd` 则**连 status 都不过**
    —— 实测把 6 条 `proposed` 条目也编译进产物。口径类改动落在这里, 不要在任一消费方
    重写一遍。
    """
    return [
        j
        for j in host_scoped_jobs(jobs)
        if j.get("status", "active") == "active" and plane in (j.get("planes") or [])
    ]


def active_crontab_jobs(jobs: list[dict]) -> list[dict]:
    """本机该编译成 crontab 的登记条目 (见 `active_plane_jobs`)。"""
    return active_plane_jobs(jobs, "crontab")

