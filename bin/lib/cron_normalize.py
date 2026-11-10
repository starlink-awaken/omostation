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
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


def _imported_names(script: Path) -> set[str] | None:
    """一个文件 import 到的顶层模块名（含函数内的懒加载）；解不开 → None."""
    dotted = _dotted_imports(script)
    return None if dotted is None else {n.split(".")[0] for n in dotted}


def _dotted_imports(script: Path) -> set[str] | None:
    """一个文件 import 到的**完整点号名**（`mypkg.inner` 保持原样）；解不开 → None.

    两份口径各有用途：顶层名判第三方（`find_spec` 只认顶层包），点号全名解析仓内
    子模块文件 —— 只按顶层名建图时，`from mypkg.inner import thing` 只能走到
    `mypkg/__init__.py`，藏在 `inner.py` 里的依赖永远读不到。
    """
    try:
        tree = ast.parse(script.read_text(errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return None
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                names.add(node.module)
    return names


def third_party_imports(script: Path) -> list[str] | None:
    """脚本顶层 import 的第三方模块名；解析不了返回 None（= 不可判定）.

    这是**发射侧口径**：只看目标脚本自己。传递依赖见 `import_closure`。
    """
    names = _imported_names(script)
    if names is None:
        return None
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
    deps_fn: Callable[[Path], list[str] | None] | None = None,
) -> tuple[str, str | None]:
    """把 command 里**每个** `python3 <script>.py` 换成本机可证可用的解释器.

    返回 `(新 command, 原因)`；原因 `None` = 每个调用点都已替换或本就无需替换。
    只在**同时满足**版本下限与目标脚本顶层第三方依赖的候选里选；某个调用点选不出
    就只留那个调用点原样，并把原因报出来（逐点判定，不整条放弃）。

    `deps_fn` 只改判据宽严（见 `_resolve_invocation`），缺省即发射侧口径。
    """
    # 缓存键必须含候选集与根: 只按 cmd 缓存会让换了 candidates/CRON_INTERPRETER 的
    # 调用读到上一个宿主布局的结果。deps 口径同样入键 —— 门禁(闭包)与安装(顶层)
    # 对同一条 cmd 的读数必须各自可取，不能互相污染缓存。
    key = (cmd, None if candidates is None else tuple(candidates),
           None if repo_root is None else str(repo_root),
           getattr(deps_fn, "__qualname__", repr(deps_fn)))
    if key in _resolve_cache:
        return _resolve_cache[key]
    result = _resolve_python_command_uncached(
        cmd, candidates=candidates, repo_root=repo_root, deps_fn=deps_fn
    )
    _resolve_cache[key] = result
    return result


def _repo_local_index(root: Path) -> dict[str, Path]:
    """仓内自有顶层模块名 → 可导入的文件/包目录（`import_closure` 的边表）.

    为什么单独列: `omo` / `repo_root` / `capability_native_sources` 这类名字不在
    任何解释器的 site-packages 里, 直接 find_spec 会误报「缺包」⇒ 拒绝切换 ⇒ 作业
    留在 3.9 的 `ImportError: cannot import name 'UTC'` 上。仓内模块的可见性与
    **解释器无关**（脚本用 `Path(__file__)` 自己插 sys.path），所以只需判断它存在。
    """
    search_dirs = [root, root / "bin", root / "src", root / "lib"]
    search_dirs += sorted(p for p in (root / "bin").iterdir() if p.is_dir()) if (root / "bin").is_dir() else []
    search_dirs += sorted((root / "projects").glob("*/src")) if (root / "projects").is_dir() else []
    found: dict[str, Path] = {}
    for d in search_dirs:
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.suffix == ".py" and e.stem != "__init__":
                found.setdefault(e.stem, e)
            elif e.is_dir() and (e / "__init__.py").is_file():
                found.setdefault(e.name, e)
    return found


_repo_local_cache: dict[str, dict[str, Path]] = {}


def _local_index_cached(root: Path) -> dict[str, Path]:
    """`_repo_local_index` 的按根缓存（同一条 cmd 在多候选探测里反复用到）。"""
    key = str(root)
    if key not in _repo_local_cache:
        _repo_local_cache[key] = _repo_local_index(root)
    return _repo_local_cache[key]


def _repo_local_modules(root: Path) -> frozenset[str]:
    """仓内自有顶层模块名 —— `_repo_local_index` 的键视图（口径只有一份实现）。"""
    return frozenset(_local_index_cached(root))


def declared_workspace(scope: str) -> tuple[Path | None, bool]:
    """`cd <dir>` 段（可能是 `$HOME` 拼法）声明的工作区 → (展开后的路径, 本机是否存在).

    取**最后一个** `cd`：shell 语义下复合命令里后面的 `cd` 覆盖前面的，拿第一个当有效
    工作区会把其后的调用点解析到错的根（脚本路径与宿主判定跟着一起错）。今天登记面
    59 条 active 作业里 0 条命中多 `cd`，是潜伏形状，不是当前误读。

    没有 cd 段返回 (None, True)：没声明过工作区，就不构成「不在本机」。存在性判的是
    **作业声明的那个目录**，不是兜底根 —— CI 的检出目录同样存在，拿兜底根当判据会把
    别人机器上的作业算到本机头上（决策(3) 落地时实测：CRON_HOST 换成跑无关的宿主，
    30 条作业照样全部进入判定）。
    """
    cd = None
    for cand in re.finditer(r"(?:^|[\s;&|])cd\s+(?P<dir>\"[^\"]+\"|[^\s;&|]+)", scope):
        cd = cand
    raw = cd.group("dir").strip('"') if cd else None
    if not raw:
        return None, True
    p = Path(os.path.expanduser(os.path.expandvars(raw)))
    return p, p.is_dir()


def _job_workspace(cmd: str, interp_start: int, fallback: Path | str | None) -> Path:
    """作业实际运行的工作区 = command 里 `cd <dir>` 的目标（可能是 `$HOME` 拼法）.

    解释器候选必须按**作业的工作区**取，而不是按编译副本自己的位置：worktree 里没有
    `.venv`，而作业永远 `cd $HOME/Workspace`（根有四类落点）。
    """
    declared, present = declared_workspace(cmd[:interp_start])
    if declared is not None and present:
        return declared
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
    m = _PYTHON_INVOCATION_RE.search(cmd)
    if m is None:
        return None
    root = _job_workspace(cmd, m.start(), repo_root)
    chosen, _reason = _resolve_invocation(m, candidates, root)
    return chosen


def _resolve_python_command_uncached(cmd, *, candidates, repo_root, deps_fn=None):
    """逐个调用点替换 —— `A && python3 B && python3 C` 里每个 python3 单独判定.

    只换第一个是 #5171 漏下的形状: 登记面有 5 条作业的 command 含 2-3 个 python
    调用点，第二个之后的脚本一旦依赖 3.11+ 就仍留在 3.9 上，而 `check_drift` 按
    折叠口径比较（解释器路径本就被折掉）永远看不见这种残留 ⇒ 必须在这里换干净。
    """
    matches = list(_PYTHON_INVOCATION_RE.finditer(cmd))
    if not matches:
        return cmd, None
    parts: list[str] = []
    reasons: list[str] = []
    pos = 0
    for m in matches:
        chosen, reason = _resolve_invocation(
            m, candidates, _job_workspace(cmd, m.start(), repo_root), deps_fn
        )
        parts.append(cmd[pos : m.start("interp")])
        parts.append(chosen if chosen is not None else m.group("interp"))
        pos = m.end("interp")
        if reason is not None:
            reasons.append(reason)
    parts.append(cmd[pos:])
    new = "".join(parts)
    return new, ("; ".join(reasons) or None)


def _resolve_invocation(
    m: re.Match[str],
    candidates: list[str] | None,
    root: Path,
    deps_fn: Callable[[Path], list[str] | None] | None = None,
) -> tuple[str | None, str | None]:
    """单个调用点 → (可用的解释器, None) 或 (None, 原因).

    `deps_fn` 决定「这个脚本需要哪些第三方包」的口径，缺省 `third_party_imports`
    (只看目标脚本自己的顶层 import) —— 发射侧 (`scheduler-compile` /
    `install-cron-plane`) 必须用缺省，否则安装结果与登记面口径分叉。可执行性门禁
    传 `import_closure` 把口径放宽到兄弟模块的传递依赖，用**同一份选择代码**得出
    「比安装侧更严」的读数；分叉只发生在判据宽严，不发生在实现。
    """
    script = Path(os.path.expanduser(os.path.expandvars(m.group("script"))))
    if not script.is_absolute():
        script = root / script
    if not script.is_file():
        return None, f"target script not found: {script}"
    deps = (deps_fn or third_party_imports)(script)
    if deps is None:
        return None, f"unparseable target: {script}"
    external = [d for d in deps if d not in _local_index_cached(root)]
    pool = candidates if candidates is not None else interpreter_candidates(root)
    for cand in pool:
        # 入选前复查可折回性: 调用方 (含 CRON_INTERPRETER) 传进不可折回的路径,
        # 会让 check_drift 把替换读成永久 drift ⇒ 宁可不换。
        if not _FOLDABLE_INTERPRETER_RE.search(cand):
            continue
        if _interpreter_ok(cand, script.parent, external):
            return cand, None
    return None, (
        f"no interpreter satisfies {script.name} (needs 3.11+ and {external or 'no third-party'}); "
        f"tried: {', '.join(pool) or '(无候选)'}"
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


def installed_crontab_lines() -> list[str] | None:
    """本机已装 crontab 的非注释行；`None` = 读不出（判不出，不是「没装」）.

    为什么需要它：可执行性是关于**这台机器跑不跑 cron 平面**的判据。CI 的 ubuntu-latest
    上 `.venv`/homebrew 都不存在，`crontab -l` 也报 no crontab for runner —— 拿那种
    解释器池去判登记面，限期那天会让每个 PR 因为一个与交付无关的理由变红。
    `check_drift` (`bin/scheduler-compile.py:248`) 与 `install-cron-plane.py:77` 各自
    跑过 `crontab -l`，但都只做「读了再比」，没有「本机到底有没有这个平面」的判定。

    返回值区分三种状态，不能都压成空列表：
      · `[]`     —— 本机确实没有 crontab（rc=1 且 stderr 是 no crontab for …）
      · `None`   —— 读不出 (crontab 不存在、EINTR、权限)，调用方不得据此判「没装」
      · 非空列表 —— 有平面，逐行内容交给调用方
    """
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 0:
        return [ln for ln in r.stdout.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if r.returncode == 1 and "no crontab for" in r.stderr:
        return []
    return None


# 形如解释器调用的 token (可无版本号)，与 INTERPRETER_RE 的区别正是后者只认 python3*。
_PYTHON_LIKE_TOKEN_RE = re.compile(r"^(?:(?:\S*/)?)(?:python\d*)(?:\.\d+)?$")
# 能被 comparison_key 折回裸 python3 的写法。
_FOLDABLE_TOKEN_RE = re.compile(r"^(?:\S*/)?python3(?:\.\d+)?$")
_SHELL_OPERATORS = frozenset({"&&", "||", ";", "|", "&"})


def _command_start_tokens(cmd: str) -> list[tuple[int, str]]:
    """返回处于**命令起始位**的 token 及其下标。

    命令起始位 = 行首、紧跟 shell 运算符之后，或紧跟 `VAR=value` 环境变量赋值之后
    (实测登记面有 `PATH=/opt/homebrew/bin:/usr/bin:/bin python3 bin/...` 这种写法)。
    只在这些位置上把 token 当解释器，避免把参数里的 `python` 字样误判成解释器。
    """
    tokens = cmd.split()
    out: list[tuple[int, str]] = []
    for i, tok in enumerate(tokens):
        if i == 0:
            out.append((i, tok))
            continue
        prev = tokens[i - 1]
        if prev in _SHELL_OPERATORS or ("=" in prev and not prev.startswith("-")):
            out.append((i, tok))
    return out


def unfoldable_interpreter_tokens(cmd: str) -> list[str]:
    """命令起始位上「像解释器但折不回裸 `python3`」的 token。

    `comparison_key` 靠 `normalize_interpreter` 把解释器写法折成 `python3` 才可比
    (`INTERPRETER_RE` 只认 `python3` / `python3.x`)。登记面若钉了 `/python`
    这种**无版本号**写法，键就永远折不回 ⇒ 安装侧把已装的另一种写法当外部行保留，
    再追加登记面那条 ⇒ 同一作业双跑 (2026-11-09 mini 实测 `local-ops-test-all`)。
    """
    bad = []
    for _i, tok in _command_start_tokens(cmd):
        if _PYTHON_LIKE_TOKEN_RE.match(tok) and not _FOLDABLE_TOKEN_RE.match(tok):
            bad.append(tok)
    return bad


def unfoldable_interpreter_jobs(jobs: list[dict]) -> list[dict]:
    """扫描本机 active crontab 条目, 列出钉了不可折回解释器的登记项。"""
    out = []
    for j in active_crontab_jobs(jobs):
        tokens = unfoldable_interpreter_tokens(expand_workspace(j.get("command", "")))
        if tokens:
            out.append(
                {
                    "name": j.get("name"),
                    "tokens": tokens,
                    "reason": "comparison_key 折不回裸 python3 ⇒ 登记面与安装态永远不可比",
                }
            )
    return out


def python_call_sites(cmd: str, *, repo_root: Path | str | None = None) -> list[dict]:
    """一条 command 里的每个 `python3 <script>.py` 调用点 → 声明写法 + 目标脚本.

    为什么要暴露出来: 登记面一条作业可以有 2-3 个 python 调用点，而“作业用的
    解释器”不是单值 —— 可执行性必须逐调用点判。与 `_resolve_invocation` 共用
    同一个正则和同一个工作区解析（`_job_workspace`），否则门禁看到的调用点会比
    安装器看到的多一个或少一个。
    """
    out: list[dict] = []
    for m in _PYTHON_INVOCATION_RE.finditer(cmd):
        root = _job_workspace(cmd, m.start(), repo_root)
        script = Path(os.path.expanduser(os.path.expandvars(m.group("script"))))
        if not script.is_absolute():
            script = root / script
        _declared, present = declared_workspace(cmd[: m.start()])
        out.append(
            {
                "declared": m.group("interp"),
                "script": script,
                "workspace": root,
                "exists": script.is_file(),
                "host_assessable": present,
            }
        )
    return out


def _load_edges(file: Path, root: Path) -> tuple[set[str], set[Path], list[Path]]:
    """一个文件的加载边 → (第三方模块名, 仓内被加载文件, 判不出的文件).

    第三项不是布尔而是**清单**：闭包里某个兄弟模块读不到（子模块没检出、包目录无
    `__init__.py`）时，把它如实列出来，让门禁能说清「哪一条判不出」。整批压成一个
    `False` 会让原因字符串指到入口脚本上 —— 那是把判据自身的故障伪装成被测物的故障。

    为什么要同时收三种形状（`CRON-BARE-PYTHON3-PY39-IMPORT-DEATH` 决策(3) 的实测依据）：
      1. `import x` / `from x import y` —— 常规形状，`third_party_imports` 已覆盖。
      2. **任意以 `.py` 结尾的字符串字面量** —— 登记面把实活交给兄弟模块时用的往往是
         `importlib.util.spec_from_file_location("gate_evidence_receipt", ROOT / "bin"
         / "gac" / "gate-evidence-receipt.py")`（实测 `bin/gac/execution-environment-steward.py:39-41`）。
         只按 import 名建图对这种形状**恒为空**，于是「入口文件顶层干净」被读成
         「这作业跑得动」—— 正是本项 2026-11-09 认出的误判来源。路径是运行时拼出来的
         (`Path` 除法链)，静态求值不出，退化成认字面量文件名，靠磁盘解析消歧。
      3. `spec_from_file_location(name, …)` / `import_module("name")` 的名字参数 ——
         同 2 的动机，取 module 名以命中仓内索引。

    方向性：2 会把「出现在参数里的 .py 文件名」也当边 ⇒ 依赖集偏**宽**。可接受，因为
    闭包口径只用于 advisory 通道（永不阻断，见 `interpreter_executability_jobs`）；
    真正的阻断判据仍是发射侧口径。宁可多报一条待看，不可漏报一种死法。
    """
    names = _imported_names(file)
    if names is None:
        return set(), set(), [file]
    index = _local_index_cached(root)
    third: set[str] = set()
    local: set[Path] = set()
    undetermined: list[Path] = []

    def _edge(target: Path) -> None:
        """索引命中 → 真能静态解析的文件（包取 `__init__.py`），否则计入判不出.

        包目录（如 `projects/omo/src/omo`）直接 `read_text` 是 `IsADirectoryError`；
        旧实现把它压成「入口 unparseable」，实测一次性误报 14 条作业 —— 判据自己的
        故障被测成了被检物的故障。
        """
        if target.is_dir():
            init = target / "__init__.py"
            if init.is_file():
                local.add(init)
            else:
                undetermined.append(target)
        elif target.is_file():
            local.add(target)
        else:
            undetermined.append(target)

    for name in names:
        target = index.get(name)
        if target is not None:
            _edge(target)
        elif name not in sys.stdlib_module_names and name != "__future__":
            third.add(name)
    # 仓内子模块：`from mypkg.inner import thing` 的点号全名要落到文件上，
    # 否则一跳只走到 `mypkg/__init__.py`，inner 里的依赖看不见。
    for dotted in sorted(_dotted_imports(file) or set()):
        parts = dotted.split(".")
        base = index.get(parts[0])
        if len(parts) < 2 or base is None or not base.is_dir():
            continue
        stem = base.joinpath(*parts[1:])
        for target in (stem.with_suffix(".py"), stem / "__init__.py"):
            if target.is_file():
                local.add(target)
                break
    try:
        tree = ast.parse(file.read_text(errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return third, local, [file]
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        val = node.value.strip()
        if val.endswith(".py"):
            for base in (file.parent, root, root / "bin", root / "bin" / "gac", root / "bin" / "lib"):
                cand = (base / val) if not Path(val).is_absolute() else Path(val)
                if cand.is_file() and root in cand.parents:
                    local.add(cand)
                    break
        elif val.isidentifier() and val in index:
            _edge(index[val])
    return third, local, undetermined


def _closure_walk(script: Path, root: Path, *, max_depth: int = 2):
    """BFS 加载图 → (第三方依赖 或 None, 判不出的文件清单).

    为什么需要它 (`CRON-BARE-PYTHON3-PY39-IMPORT-DEATH` 决策(3) 缺的单位):
    `third_party_imports` 只看目标脚本自己**顶层 import 的名字**，而登记面常把实活交给
    兄弟模块，且兄弟模块是**动态按路径加载**的 —— 实测
    `bin/gac/execution-environment-steward.py:39-41` 用
    `spec_from_file_location(..., ROOT / "bin" / "gac" / "gate-evidence-receipt.py")`
    拉起 `bin/gac/gate-evidence-receipt.py`，后者顶层 `import yaml`。只按 import 名建图
    对这条边**恒为空**，于是「入口文件顶层干净」被读成「这作业跑得动」——正是本项
    2026-11-09 认出的误判来源。以「入口文件自身」为口径的任何补计或门禁都必然低报。

    仍然**不执行目标脚本**（本模块不变量 2）：只 ast 解析；模块级副作用（网络/写盘，
    登记面里确实有 POST git、递归删目录、mem0 purge 这类作业）一概不碰。
    `max_depth=1` 时只剩入口自己这一跳；环靠 visited 集合阻断。
    """
    deps: set[str] = set()
    seen: set[Path] = set()
    undetermined: list[Path] = []
    frontier: list[tuple[Path, int]] = [(script, 1)]
    while frontier:
        current, depth = frontier.pop(0)
        try:
            key = current.resolve()
        except OSError:
            key = current
        if key in seen:
            continue
        seen.add(key)
        third, local, bad = _load_edges(current, root)
        deps |= third
        undetermined += [p for p in bad if p not in undetermined]
        if depth < max_depth:
            frontier.extend((p, depth + 1) for p in local)
    entry_bad = script in undetermined or _imported_names(script) is None
    return (None if entry_bad else sorted(deps)), undetermined


_closure_cache: dict[tuple[str, str, int], tuple[list[str] | None, list[Path]]] = {}


def _closure_of(script: Path, root: Path, max_depth: int):
    key = (str(script), str(root), max_depth)
    if key not in _closure_cache:
        _closure_cache[key] = _closure_walk(script, root, max_depth=max_depth)
    return _closure_cache[key]


def import_closure(script: Path, root: Path, *, max_depth: int = 2) -> list[str] | None:
    """闭包口径的第三方依赖；**入口脚本自己**判不出才返回 None.

    None 的语义与 `third_party_imports` 对齐（= 不可判定），兄弟模块判不出**不**降级成
    None —— 那会让 14 条作业的原因串指到入口文件上。兄弟侧的判不出走
    `closure_undetermined`，由门禁如实列出。
    """
    return _closure_of(script, root, max_depth)[0]


def closure_undetermined(script: Path, root: Path, *, max_depth: int = 2) -> list[str]:
    """闭包里静态判不出的文件（子模块未检出 / 包无可解析入口 / 语法错误）。"""
    return [str(p) for p in _closure_of(script, root, max_depth)[1]]


def interpreter_executability_jobs(
    jobs: list[dict],
    *,
    candidates: list[str] | None = None,
    repo_root: Path | str | None = None,
    max_depth: int = 2,
    installed_plane: list[str] | None | Any = ...,
) -> list[dict]:
    """本机 active crontab 条目的解释器可执行性读数（决策(3) 的门禁判据）。

    每条作业给两个口径，**都报，不取并集成一个数**：
      · `install_reason` —— 发射侧口径 (`third_party_imports`)。非 None 就是真缺口：
        安装器解不出可用解释器 ⇒ 那条 cron 行留在裸 `python3` 上，到 3.9 就死。
      · `closure_reason` —— 闭包口径 (`import_closure`)。比发射侧更严；只有它报而
        发射侧不报 = 依赖藏在兄弟模块里，装上了也可能在某天实跑时 `ImportError`。

    退出码只由 `install_reason` 决定（它才是「装上去会不会死」的权威读数），
    `closure_reason` 单独计数，见 `bin/gac/check-cron-interpreter-executability.py`。

    `host_assessable=False` 的记录不参与任何判定，也不跑探测，两种原因都算：
      · 作业声明的工作区不在本机（换机、登记面写了本机没有的路径）；
      · 本机根本没装 cron 平面 —— CI 的 ubuntu-latest 上 `crontab -l` 报
        `no crontab for runner`，`.venv`/homebrew 也都不存在。把它当缺口，限期到期那天
        每个 PR 都会因为一个与交付无关的理由变红，而不是让该修的宿主变红。
    `installed_plane` 缺省 `...` = 读本机；调用方可注入列表/None（测试与非 crontab 消费方）。
    """
    import functools

    plane = installed_crontab_lines() if installed_plane is ... else installed_plane
    # 读不出 (None) 时保守照判：「判不出」不等于「没装」，不能拿仪器的故障当被检物的清白。
    on_plane = True if plane is None else bool(plane)

    out: list[dict] = []
    for j in active_crontab_jobs(jobs):
        cmd = expand_workspace(j.get("command", ""))
        sites = python_call_sites(cmd, repo_root=repo_root)
        if not sites:
            continue  # 该作业没有 python 调用点：解释器判据不适用，不算通过也不算缺口
        record = {
            "name": j.get("name"),
            "schedule": j.get("schedule"),
            "owner": j.get("owner"),
            "sites": [
                {"declared": s["declared"], "script": str(s["script"]), "exists": s["exists"]}
                for s in sites
            ],
            "host_assessable": on_plane and all(s["host_assessable"] for s in sites),
            "install_reason": None,
            "closure_reason": None,
        }
        if record["host_assessable"]:
            _new, record["install_reason"] = resolve_python_command(
                cmd, candidates=candidates, repo_root=repo_root
            )
            _new, record["closure_reason"] = resolve_python_command(
                cmd,
                candidates=candidates,
                repo_root=repo_root,
                deps_fn=functools.partial(import_closure, root=_root_of(repo_root), max_depth=max_depth),
            )
        out.append(record)
    return out


def _root_of(repo_root: Path | str | None) -> Path:
    """缺省根 = 本仓（与 `interpreter_candidates` 的缺省一致，不另立一份）。"""
    return Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]

