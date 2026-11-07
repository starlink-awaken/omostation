"""omo.resident 写者解析根 vs bin/ 读者解析根 的跨仓对照。

契约: `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` (D1/D3)
BET:  BET-Y2Q4-T10-233   spec: `docs/superpowers/specs/2026-06-06-omo-resident-write-plane-state-root.md`

判据-5 要求「逐路径输出写者解析根 vs 读者解析根」并把允许的不对称钉成**集合相等**。
本文件同时钉住三件事，缺一件就会留下「写面迁了、读者还在原地，而两边测试都绿」的缝:

- **写侧**: omo 里哪些路径族真的经 resolver 落到 state 根 (`STATE_FAMILIES`)，哪些 resident
  模块**故意**留在检出根 (`DEFERRED_RESIDENT_WRITERS` + 协调面例外)。
- **读侧**: bin/ 对每个 state 族读到的是哪个根 (`SPLIT_EXACT` / `SPLIT_ANCESTOR`，含根类别)。
- **两仓同一 ledger 口径**: `bin/lib/repo_root.event_ledger_path()` 与
  `projects/omo/src/omo/omo_paths.event_ledger_path()` 在每个 env 配置下**逐字节相等** ——
  这条只能靠**执行**验，扫源码扫不出「两个都对但拼法不同」。

⚠️ 现状 (四次移动: T10-233 初判 → T10-247 → 2026-10-29 bin/ 读侧收敛 → 2026-11-02 声明补全):
T10-233 基线上 bin/ 侧**没有任何读者**解析到 state 根 (类别只有 CHECKOUT / CALLER / DERIVED)，
因此「读写同根」在不动 `bin/` 的前提下**结构上不可能达成**；台账 circuit_breaker 明确
「需要改 bin/ 读者 → 停下登记而不是扩大 PR」，所以当时这里是登记，不是豁免的省略。
T10-247 把 projection-full-refresh 的 ledger 第②支落到 state 根，2026-10-29 把
`.omo/_delivery/resident-orchestrator/**` 一族两个文件里的四处访问器改为调用时刻解析 —— 于是
「零读者」这句**按事实不再成立**，读侧改为钉 `REVIEWED_STATE_READERS` 评审集。
**本族已读写同根**；其余族仍是**已登记的 split 现状**，`log-rotate.py` 按设计留在检出根并由
`tests/unit/test_resident_plane_readers_state_root.py::test_log_rotate_stays_registered` 钉住 ——
它清的是祖先目录，漏改的后果不是读不到而是旧文件永不清理。

2026-11-02: omo 写面自 2026-10-10 (T10-239) 起从 18 族长到 42 族 (resident 状态面 + `_knowledge`
jsonl 面)，而本文件的登记表一直停在 18 —— 这就是 BET-Y2Q4-T10-277 §4 记的「声明 18 / 实扫 42
的口径缺口」，挂了 3 周无人看见 (根 `governance-check.yml` 是逐文件白名单，不含 `tests/unit/**`)。
本轮把写侧族表、读侧 split 表、CALLER/DERIVED 证据表**全部按实测补齐**，并顺手补上检测器的
两个分类盲区 (`X = code_root()` 与模块级别名链) —— 不补的话，活面里可判的站点会被误报成
「未知根」。

开发期读的是 `projects/omo` (分支 gitlink 的检出)；未 bump-pointer 时那份还没有写面机制，
`test_omo_checkout_carries_the_write_plane_mechanism` 会当场红并指名原因。用
`OMO_RESIDENT_SRC` 指向 `.subtrees/omo/src/omo` 可在 bump 之前跑同一份判据。
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "bin"
# 开发期 seam: `OMO_RESIDENT_SRC=<worktree>/.subtrees/omo/src/omo` 让同一份判据在
# bump-pointer 之前就能跑迁移后的源码; CI/常规跑不带它, 读分支 gitlink 的 projects/omo。
OMO_SRC = Path(os.environ.get("OMO_RESIDENT_SRC") or (ROOT / "projects" / "omo" / "src" / "omo"))
DEFAULT_OMO_SRC = ROOT / "projects" / "omo" / "src" / "omo"
REPO_ROOT_PY = ROOT / "bin" / "lib" / "repo_root.py"
OMO_PATHS_PY = OMO_SRC / "omo_paths.py"

# ── 解析器 (被测面) ───────────────────────────────────────────────────────

RESOLVERS = frozenset({"write_path", "state_root", "event_ledger_path", "state_file_read"})
_STATE_MARKERS = ("state_root", "runtime_state_root", "state_file_read", "projection_read", "event_ledger_path")
# 检出锚点标记 —— 与 CALLER_EVIDENCE 的 `checkout: True` 判据**同一份**。
# 2026-11-02: `_classify` 原先只认 `__file__`/`parents[` 两个字面量, 于是
# `WORKSPACE = code_root()` 被判 DERIVED —— 而 `code_root()` 就是
# `Path(__file__).resolve().parents[2]` (repo_root.py:87-89)。同一份标记两处用两个口径,
# 是「判据与被检对象不同源」的形状, 所以这里收成一份。
CHECKOUT_MARKERS = ("__file__", "parents[", "code_root")
_COORDINATION = ".omo/_delivery/agent-workflows"


def _chain(node: ast.AST) -> list[ast.AST]:
    """按**源码顺序**递归展平 `/` 链 (ast.walk 是 BFS，用它拼出的片段顺序是错的)。"""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _chain(node.left) + _chain(node.right)
    return [node]


def _text(segments: list[ast.AST]) -> str:
    out = []
    for seg in segments:
        if isinstance(seg, ast.Constant) and isinstance(seg.value, str):
            out.append(seg.value.strip("/"))
        else:
            out.append("*")
    return "/".join(p for p in out if p)


def _anchor(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return f.attr
    return None


def _repo_path(text: str) -> bool:
    return text.startswith(".omo/") or text.startswith("runtime/")


def _classify(value: ast.AST) -> str:
    """模块级名字的**根类别**。故意只有四类，第四类根 (CWD) 不在这里 —— 见下方 RELATIVE 类目的注释。

    `RELATIVE` 不是这个函数的一个分支，两个原因，都是量出来的而不是推理：
    ① 这里拿到的只有**值表达式**，没有用法，因而无法区分「根」与「后缀」。
       `bin/lib/repo_root.py` 的 `LEDGER_RELATIVE = Path("runtime/omo/event-ledger.sqlite3")`
       按值形状命中 spec §5 AC-01 (b)，但它实际是 `state_root() / LEDGER_RELATIVE` 的**后缀片段** ——
       按值判会把 33 个 bin 侧片段判成 CWD 根 (本轮实测)，其中绝大多数根本不是根。
    ② 读侧不缺这一类：`reader_pairs` 的 223 行里，锚点是仓内相对量的**零行** (本轮实测 klass
       差集 = 0)，即加进来是一个在真实树上永不发火的装饰性分支 (§7③「按构造就绿」的反面)。
    所以第四类根在尺 A 的落点是**写侧桶** (`scan_writers` 的第 5 桶 `relative`)，判据带用法。
    """
    d = ast.dump(value)
    if any(k in d for k in _STATE_MARKERS):
        return "STATE"
    if any(k in d for k in CHECKOUT_MARKERS):
        return "CHECKOUT"
    if "environ" in d or "getenv" in d:
        return "EXTERNAL"
    return "DERIVED"


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _module_classes(path: Path, cache: dict[Path, dict[str, str]]) -> dict[str, str]:
    """模块级 `NAME = <expr>` 的根类别。

    含两条解析链: ① 同模块 `A = B` 别名 (B 的类别就是 A 的); ② 一跳 sibling import
    (`from _shared import ROOT`)。

    2026-11-02: ①是补的 —— `SCRIPT_DIR = Path(__file__).parent` +
    `WORKSPACE_ROOT = SCRIPT_DIR.parent.parent` 原先被判 DERIVED, 而它显然是检出根。
    别名链不展开时, 「未知根混进活面」的判据会把**可判的**站点误报成不可判。
    """
    if path in cache:
        return cache[path]
    cache[path] = {}
    tree = _parse(path)
    if tree is None:
        return cache[path]
    cls: dict[str, str] = {}
    imported: dict[str, str] = {}
    values: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and node.value is not None:
                    values[t.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            values[node.target.id] = node.value
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                imported[a.asname or a.name] = node.module

    def _root_name(node: ast.AST) -> str | None:
        """表达式最底层那个名字 —— `SCRIPT_DIR.parent.parent` 的根是 `SCRIPT_DIR`。"""
        while True:
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, (ast.Attribute, ast.Call)):
                node = node.func if isinstance(node, ast.Call) else node.value
                continue
            return None

    def resolve(name: str, seen: frozenset[str]) -> str:
        if name in cls:
            return cls[name]
        if name in seen:
            return "DERIVED"
        node = values.get(name)
        if node is None:
            return "DERIVED"
        cls[name] = _classify(node)
        if cls[name] == "DERIVED" and (root := _root_name(node)) is not None:
            cls[name] = resolve(root, seen | {name})
        return cls[name]

    for name in values:
        resolve(name, frozenset())
    cache[path] = cls
    for name, mod in imported.items():
        if name in cls:
            continue
        cand = path.parent / (mod.replace(".", "/") + ".py")
        if cand.is_file():
            cls[name] = _module_classes(cand, cache).get(name, "DERIVED")
    return cls


def _fallback_alias(tree: ast.AST) -> dict[str, str]:
    """`root = root or ROOT` 这类兜底：小写参数名 → 同函数里的模块常量名。"""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.BoolOp) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name):
                for v in node.value.values:
                    if isinstance(v, ast.Name) and v.id != t.id:
                        out[t.id] = v.id
    return out


def _outermost_divs(tree: ast.AST) -> set[int]:
    """`a / b / c` 里内层的 `a / b` 不是独立路径表达式 —— 不排掉就会造出 4 条虚族。"""
    inner: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            for sub in (node.left, node.right):
                if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):
                    inner.add(id(sub))
    return inner


def _module_level_nodes(tree: ast.AST) -> set[int]:
    """模块级赋值里的表达式：那是**模板常量**（`write_path()` 的输入），不是写点。"""
    ids: set[int] = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            ids.update(id(sub) for sub in ast.walk(node))
    return ids


def _strip_dynamic(text: str) -> str:
    return text.rstrip("/")


def _resolver_call_families(tree: ast.AST, templates: dict[str, str]) -> dict[str, list[str]]:
    """resolver 调用参数解析出的路径族；参数是别的调用时记 `@OPAQUE:<callee>`。"""
    found: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _anchor(node.func) in RESOLVERS):
            continue
        for arg in node.args:
            if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Div):
                text = _strip_dynamic(_text(_chain(arg)[1:]))
                if _repo_path(text):
                    found.setdefault(text, []).append("resolver-inline")
            elif isinstance(arg, ast.Name) and arg.id in templates:
                found.setdefault(templates[arg.id], []).append(f"resolver:{arg.id}")
            elif isinstance(arg, ast.Call):
                found.setdefault(f"@OPAQUE:{_anchor(arg.func) or '?'}", []).append("resolver-opaque")
    return found


def _templates(tree: ast.AST) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        segs = _chain(node.value) if isinstance(node.value, ast.BinOp) else []
        for t in node.targets:
            if isinstance(t, ast.Name) and len(segs) >= 2:
                text = _strip_dynamic(_text(segs[1:]))
                if _repo_path(text) and _anchor(segs[0]) not in RESOLVERS:
                    out[t.id] = text
    return out


# ── RELATIVE 类目 (BET-Y2Q4-T10-288, spec §5 AC-01) —— 第四类根：不挂任何根的仓内相对锚 ──────
#
# 这尺原先按构造看不见这类根，机制是 spec §3 前两条，都在这个文件自己身上：
# ① **尾段比较** —— `_text(segs[1:])` 丢掉 `segs[0]`（锚）再比对族名，于是
#    `Path(".omo") / "state" / "x"` 的比较串是 `state/x`，既过不了 `_repo_path()` 也匹配不上任何族；
# ② **只走 `Div` 节点** —— `bin/notification.py:35` 那种单个 `Path(...)` 调用连候选都不是。
# 所以这里补的是**并列**的第五桶，不是把前四桶的准入放宽：前四桶的读数逐字节未变
# （由本文件已有的 `STATE_FAMILIES` / `DEFERRED_RESIDENT_WRITERS` / `OPAQUE_WRITERS` 等断言钉着），
# 第四类根站点原先不在任何桶里，现在只进 `relative`。
#
# 判据与被检对象**同源**：与 `tests/unit/test_writeplane_root_pin.py` 的相对锚检测器同一份语义
# （函数名逐一对应），并由 `test_two_rulers_agree_on_the_relative_face` 在 bin 面上双向对拍 ——
# 两份各写一遍而不对拍，就是 AGENTS.md §7「检测器的分类规则要与标记清单同源」的下一个事故。
RELATIVE_ROOTS = (".omo/", "runtime/")
RELATIVE_CONSTRUCTORS = frozenset({"Path", "join"})
ENV_READERS = frozenset({"get", "getenv"})
RELATIVE_SKIP_SEGMENTS = {"_archive", "_vendored", "__pycache__", ".venv"}
ROOT_ACTION_ATTRS = frozenset(
    {
        "mkdir", "write_text", "write_bytes", "read_text", "read_bytes", "touch",
        "unlink", "rmdir", "chmod", "replace", "rename", "glob", "rglob", "iterdir",
        "exists", "is_file", "is_dir", "open", "stat", "resolve", "link_to", "samefile",
    }
)
FS_CALLS = frozenset({"open", "exists", "isfile", "isdir", "makedirs", "mkdir", "remove", "rmtree", "copy", "copyfile"})


def _segments(node: ast.AST, bindings: dict[str, ast.AST], seen: frozenset[str] = frozenset()) -> list[str]:
    """按源码顺序展平一条路径表达式的段；判不出来的段记 `*`（AC-03 的派生链就走这条路）。"""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _segments(node.left, bindings, seen) + _segments(node.right, bindings, seen)
    if isinstance(node, ast.Constant):
        return [node.value] if isinstance(node.value, str) else ["*"]
    if isinstance(node, ast.Name):
        value = bindings.get(node.id)
        if value is None or node.id in seen:
            return ["*"]  # 形参 / 别处进来的根 / 自指 —— 落点不由本表达式决定
        return _segments(value, bindings, seen | {node.id})
    if isinstance(node, ast.Call):
        fname = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if fname in ENV_READERS:
            lits = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            return [lits[-1]] if lits else ["*"]  # 末位字面量 = 默认值，它才是 env 未声明时的落点
        if fname == "Path" and len(node.args) == 1:
            return _segments(node.args[0], bindings, seen)
        if fname == "join":
            out: list[str] = []
            for arg in node.args:
                out.extend(_segments(arg, bindings, seen))
            return out
        return ["*"]
    return ["*"]


def _literal_head(segments: list[str]) -> str:
    parts: list[str] = []
    for seg in segments:
        if seg == "*":
            break
        seg = seg.strip("/")
        if seg and seg != ".":
            parts.append(seg)
    return "/".join(parts)


def _relative_root(segments: list[str]) -> str | None:
    head = _literal_head(segments)
    return head if head.startswith(RELATIVE_ROOTS) else None


def _path_bindings(scope: ast.AST) -> dict[str, ast.AST]:
    """`NAME = <expr>` 登记，模块级与函数内都要 —— AC-03 那条链 (`STATE_DIR → state_dir`) 是过程内的。"""
    found: list[tuple[int, str, ast.AST]] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and node.value is not None:
                    found.append((node.lineno, t.id, node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            found.append((node.lineno, node.target.id, node.value))
    out: dict[str, ast.AST] = {}
    for _ln, name, value in found:
        out.setdefault(name, value)
    return out


def _leftmost(node: ast.AST) -> ast.AST:
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        node = node.left
    return node


def _parent_map(scope: ast.AST) -> dict[int, ast.AST]:
    par: dict[int, ast.AST] = {}
    for node in ast.walk(scope):
        for child in ast.iter_child_nodes(node):
            par[id(child)] = node
    return par


def _callee_defs(scope: ast.AST) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in ast.walk(scope) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _assign_target_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _param_is_root(fn: ast.FunctionDef, param: str, depth: int = 0) -> bool:
    return _name_is_root(param, fn, _path_bindings(fn), _parent_map(fn), _callee_defs(fn), depth + 1)


def _name_is_root(
    name: str,
    scope: ast.AST,
    bindings: dict[str, ast.AST],
    par: dict[int, ast.AST],
    defs: dict[str, ast.FunctionDef],
    depth: int = 0,
) -> bool:
    for node in ast.walk(scope):
        if not (isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)):
            continue
        if _expr_is_root(node, scope, par, bindings, defs, depth):
            return True
    return False


def _expr_is_root(
    node: ast.AST,
    scope: ast.AST,
    par: dict[int, ast.AST],
    bindings: dict[str, ast.AST],
    defs: dict[str, ast.FunctionDef],
    depth: int = 0,
) -> bool:
    """这个相对值是**被当根用**（落点由它 = 进程 CWD）还是只当后缀拼上去（落点由被拼的那棵树）。

    只正面枚举决定落点的用法：R1 链最左、R2 路径动作的接收者、R3 fs 调用的直接实参、
    R5 一跳进本模块 callee。默认 False —— 反过来写会在每一种没枚举到的父节点形状上假阳
    （尺 B 本轮实测两处：元组比较里的 `x.parent in (Path(".omo/_control"), …)`、`path = value or default`
    的默认实参）。
    """
    if depth > 3:
        return False
    p = par.get(id(node))
    if p is None:
        return False
    while isinstance(p, (ast.Tuple, ast.List, ast.Set)):
        p = par.get(id(p))
        if p is None:
            return False
    if isinstance(p, ast.BoolOp):
        target = _assign_target_name(p)
        if target is None:
            return False
        return _name_is_root(target, scope, bindings, par, defs, depth + 1)
    if isinstance(p, ast.Attribute):
        return p.attr in ROOT_ACTION_ATTRS
    if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div):
        if _leftmost(p) is node:
            return True
        base = _leftmost(p)
        bname = ""
        if isinstance(base, ast.Call):
            bname = base.func.id if isinstance(base.func, ast.Name) else getattr(base.func, "attr", "")
        if bname in RELATIVE_CONSTRUCTORS:
            return _relative_root(_segments(base, bindings)) is not None
        return False
    if isinstance(p, ast.Call):
        fname = p.func.id if isinstance(p.func, ast.Name) else getattr(p.func, "attr", "")
        if fname in FS_CALLS:
            return True
        if depth >= 2:
            return False
        fn = defs.get(fname)
        if fn is None:
            return False
        params = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
        received: list[str] = []
        for i, arg in enumerate(p.args):
            if arg is node and i < len(params):
                received.append(params[i])
        for kw in p.keywords:
            if kw.value is node and kw.arg in params:
                received.append(kw.arg)
        return any(_param_is_root(fn, name, depth) for name in received)
    return False


def _relative_in_file(rel: str, tree: ast.AST, shapes: tuple[str, ...]) -> dict[str, tuple[str, int, str]]:
    """单文件的相对锚根：`{family: (src 相对文件, 首次命中行号, 形名)}`，按根去重（登记单位是根，不是每次拼接）。"""
    bindings = _path_bindings(tree)
    par = _parent_map(tree)
    defs = _callee_defs(tree)
    cands: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if "chain" not in shapes:
                continue
            rroot = _relative_root(_segments(_leftmost(node), bindings))
            if rroot is not None:
                cands.append((node.lineno, rroot, "chain"))
            continue
        if not isinstance(node, ast.Call) or "call" not in shapes:
            continue
        fname = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        if fname not in RELATIVE_CONSTRUCTORS:
            continue
        rroot = _relative_root(_segments(node, bindings))
        if rroot is None:
            continue
        holders = [
            t.targets[0].id
            for t in ast.walk(tree)
            if isinstance(t, ast.Assign) and getattr(t, "value", None) is node
            and len(t.targets) == 1 and isinstance(t.targets[0], ast.Name)
        ]
        if holders and not _name_is_root(holders[0], tree, bindings, par, defs):
            continue  # 只当后缀 ⇒ 这一处不是 CWD 根（`LEDGER_RELATIVE` 那一形）
        if not holders and not _expr_is_root(node, tree, par, bindings, defs):
            continue
        cands.append((node.lineno, rroot, "call"))
    out: dict[str, tuple[int, str]] = {}
    for lineno, rroot, shape in sorted(cands):
        if rroot in out or not _repo_path(rroot):
            continue
        out[rroot] = (lineno, shape)
    return {fam: (rel, line, shape) for fam, (line, shape) in out.items()}


def scan_relative_writers(src: Path, shapes: tuple[str, ...] = ("chain", "call")) -> dict[str, list[tuple[str, int, str]]]:
    """第四类根站点：`{family: [(src 相对文件, 行号, 形名)]}，形名 ∈ chain|call。"""
    buckets: dict[str, list[tuple[str, int, str]]] = {}
    for path in sorted(src.rglob("*.py")):
        if set(path.relative_to(src).parts) & RELATIVE_SKIP_SEGMENTS:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        rel = str(path.relative_to(src))
        for fam, hit in _relative_in_file(rel, tree, shapes).items():
            buckets.setdefault(fam, []).append(hit)
    return buckets


def scan_writers(src: Path) -> dict[str, dict[str, list[tuple[str, int, str]]]]:
    """src/**.py → {bucket: {family: [(file, line, kind)]}}, bucket ∈ state|bare_template|bare_inline|opaque|relative。"""
    buckets: dict[str, dict[str, list[tuple[str, int, str]]]] = {
        "state": {},
        "bare_template": {},
        "bare_inline": {},
        "opaque": {},
        "relative": {},
    }
    for path in sorted(src.rglob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        rel = str(path.relative_to(src))
        templates = _templates(tree)
        inner = _outermost_divs(tree)
        module_nodes = _module_level_nodes(tree)
        for family, kinds in _resolver_call_families(tree, templates).items():
            for kind in kinds:
                if kind == "resolver-opaque":
                    buckets["opaque"].setdefault(family, []).append((rel, 0, kind))
                else:
                    buckets["state"].setdefault(family, []).append((rel, 0, kind))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
                continue
            if id(node) in inner or id(node) in module_nodes:
                continue
            segs = _chain(node)
            text = _strip_dynamic(_text(segs[1:]))
            if not _repo_path(text):
                continue
            anchor = _anchor(segs[0])
            if anchor in RESOLVERS:
                buckets["state"].setdefault(text, []).append((rel, node.lineno, "state-anchored"))
            else:
                buckets["bare_inline"].setdefault(text, []).append((rel, node.lineno, anchor or "?"))
        for name, text in templates.items():
            buckets["bare_template"].setdefault(text, []).append((rel, 0, f"template:{name}"))
        if not set(path.relative_to(src).parts) & RELATIVE_SKIP_SEGMENTS:
            for fam, hit in _relative_in_file(rel, tree, ("chain", "call")).items():
                buckets["relative"].setdefault(fam, []).append(hit)
    return buckets


# ── AC-05 族表闭合性 (BET-Y2Q4-T10-289, spec §7 AC-05) ────────────────────
#
# spec §5 的结论是「`STATE_FAMILIES` 与读者名单**都不是闭合集**」，所以本文件的分桶读数不能被当成
# 「全部的面都在表里」。这条判据把那句话变成能跑的尺：挂在 state 根上、族表却没登记的面 ⇒ 点名。
# 两个细节都是从量出来的而不是推出来的：
# ① **容器族只覆盖它自己**。`.omo/_knowledge` 登记为族（`omo_logs.knowledge_dir()` 那条裁决），
#    但它不替后代声明「已登记」—— 否则 `workflow-mesh/journey-states` 会被容器顺带盖掉，
#    与尺 B 的 AC-02 是同一个形状的错误（用容器判等于整串排除）。
# ② 分桶按**形状**收集，读写不分。今天点名的两条都是 `root_state / ... .glob()` 形态的读点，
#    所以这条尺子证的是「族表闭合性」，不是「谁在写」。把它读成写者名单就是 §7「判据报警先 print
#    原始行再定性」的下一次事故。

CONTAINER_FAMILIES = frozenset({".omo/_knowledge"})


def _family_covers(plane: str) -> str | None:
    """族表登记了这个平面吗？返回命中的族名；没登记 ⇒ None。通配族覆盖它前缀下的一切。"""
    for fam in STATE_FAMILIES:
        if fam in CONTAINER_FAMILIES:
            if plane == fam:
                return fam
            continue
        if fam.endswith("/*"):
            base = fam[:-2]
            if plane == base or plane.startswith(base + "/"):
                return fam
        elif plane == fam or plane.startswith(fam + "/"):
            return fam
    return None


def _anchor_is_state_root(src: Path, rel: str, anchor: str) -> bool:
    """锚点变量在本文件里是否绑到 profile 解析器 —— 判据与 `_classify` 共用 `_STATE_MARKERS`。"""
    tree = _parse(src / rel)
    if tree is None or not anchor.isidentifier():
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == anchor for t in node.targets
        ) and any(marker in ast.dump(node.value) for marker in _STATE_MARKERS):
            return True
    return False


def state_root_planes_without_family(src: Path) -> dict[str, list[tuple[str, int, str]]]:
    """`src/**.py` 里挂在 state 根上、却不被族表覆盖的面 ⇒ {平面: [(文件, 行, 来源桶)]}。

    两个来源桶都要扫：`state` 桶（resolver 直接命中）与 `bare_inline` 桶里锚点确实绑到 profile
    解析器的那些（`root_state = state_root()` 这类别名，resolver 匹配不到变量名本身）。
    只扫 `state` 桶的话，本轮 spec §5 点名的 `journey-states` 会再次漏掉 —— 它在 `bare_inline`。
    """
    buckets = scan_writers(src)
    out: dict[str, list[tuple[str, int, str]]] = {}
    for plane, items in buckets["state"].items():
        if _family_covers(plane) is None:
            out[plane] = [(rel, line, "state") for rel, line, _kind in items]
    for plane, items in buckets["bare_inline"].items():
        if _family_covers(plane) is not None:
            continue
        hits = [
            (rel, line, f"bare_inline:{anchor}")
            for rel, line, anchor in items
            if _anchor_is_state_root(src, rel, anchor)
        ]
        if hits:
            out[plane] = hits
    return out


def reader_pairs(src: Path, families: set[str]) -> list[tuple[str, str, str, int, str, str]]:
    """bin/**.py 里对 families 的读取: (family, kind, rel_file, line, anchor, root_class)。

    kind: exact = 等于族或族的后代; ancestor = 读取点是族的**严格祖先目录**。
    """
    fams = sorted(f for f in families if not f.startswith("@OPAQUE:"))
    rows: list[tuple[str, str, str, int, str, str]] = []
    cache: dict[Path, dict[str, str]] = {}
    for path in sorted(src.rglob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        rel = str(path.relative_to(src.parent))
        cls = _module_classes(path, cache)
        alias = _fallback_alias(tree)
        inner = _outermost_divs(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
                continue
            if id(node) in inner:
                continue
            segs = _chain(node)
            anchor = _anchor(segs[0])
            if anchor is None:
                continue
            text = _strip_dynamic(_text(segs[1:]))
            if "/" not in text:
                continue
            klass = "STATE" if anchor in RESOLVERS else cls.get(anchor)
            if klass is None and anchor in alias:
                klass = cls.get(alias[anchor], "CALLER")
            if klass is None:
                klass = "CALLER" if anchor.islower() else "DERIVED"
            for fam in fams:
                if text == fam or text.startswith(fam + "/"):
                    rows.append((fam, "exact", rel, node.lineno, anchor, klass))
                elif fam.startswith(text + "/") and text.count("/") >= 2:
                    rows.append((fam, "ancestor", rel, node.lineno, anchor, klass))
    return rows


def _group(rows, kind):
    """split = 写者落 state 根、读者**不**在 state 根。类别为 STATE 的读取点不构成 split。"""
    out: dict[str, set[tuple[str, str]]] = {}
    for fam, k, rel, _line, _anchor, klass in rows:
        if k == kind and klass != "STATE":
            out.setdefault(fam, set()).add((rel, klass))
    return out


def _state_readers(rows):
    return sorted({(rel, line) for _f, _k, rel, line, _a, klass in rows if klass == "STATE"})


# ── checkout_resolver 谓词: 「某个 repo_root 公开 callable 是不是检出根定位器」──────────
#
# 五条**全部**由 AST 判定，不 import repo_root（import 会把 host 状态带进探测面，
# 见 AGENTS.md §7「hermetic 测试泄漏 host 状态」），不做子串比较。为什么不能用子串（本轮实测）：
# `"__file__" in ast.unparse(canonical_root)` 读数为 **True**，只因它那句 RuntimeError 的
# **文案**里写着 `__file__`；反向同源失误是 `code_root` —— `Path(__file__)` 里 `__file__` 是
# Name 作实参，只查 `X.__file__` 的 Attribute 判据对它**恒 False**。两种形状都要查。
#
# 为什么是五条而不是三条：三条（原 spec 草案）的通过集实测是 `{canonical_root, projection_rels}`
# —— projection_rels 是投影路径查询器，不是检出根定位器，被当证据就是橡皮章。

_CHECKOUT_CLAUSES = ("no-file-anchor", "no-state-marker", "refs-marker", "raises", "zero-required-args")


def _violated_clauses(fn: ast.FunctionDef) -> list[str]:
    """返回 fn 违反的条款；空列表 = 五条齐备 = 合格定位器。"""
    out: list[str] = []
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    attrs = [a for a in ast.walk(fn) if isinstance(a, ast.Attribute)]
    file_anchored = "__file__" in names or any(
        isinstance(a.value, ast.Name) and a.value.id == "__file__" for a in attrs
    )
    if file_anchored:
        out.append("no-file-anchor")
    if (names | {a.attr for a in attrs}) & set(_STATE_MARKERS):
        out.append("no-state-marker")
    if "MARKER" not in names and "MARKER" not in {a.attr for a in attrs}:
        out.append("refs-marker")
    if not any(isinstance(r, ast.Raise) for r in ast.walk(fn)):
        out.append("raises")
    a = fn.args
    required = len(a.posonlyargs) + len(a.args) - len(a.defaults)
    if required > 0 or any(d is None for d in a.kw_defaults):
        out.append("zero-required-args")
    return out


def _all_names(tree: ast.AST) -> set[str]:
    """从 AST 取 `__all__` 字面量，不 import 被测模块。"""
    for node in tree.body:
        # Assign 是 targets（复数、可链式解包），AnnAssign 才是 target；先按类型筛再取属性 ——
        # 直接 getattr 会让模块级 docstring(Expr) 也走一遍，当场 AttributeError。
        if isinstance(node, ast.Assign):
            names = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            names = [node.target]
        else:
            continue
        for t in names:
            if isinstance(t, ast.Name) and t.id == "__all__":
                return set(ast.literal_eval(node.value))
    raise AssertionError("repo_root.py 没有 __all__ 字面量")


def _checkout_anchored_resolver(name: str, *, src: Path = REPO_ROOT_PY) -> tuple[bool, list[str], str]:
    """name 必须是 src 里 `__all__` 声明的模块级 callable；返回 (合格, 违反条款, 函数体)。"""
    tree = _parse(src)
    assert tree is not None, src
    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if name not in _all_names(tree) or not defs:
        return False, ["not-a-public-callable"], ""
    fn = defs[0]
    return (not (violated := _violated_clauses(fn)), violated, ast.unparse(fn))


# 合法最小体（等价于 canonical_root 的形状）—— 只断言「全拒绝」时谓词恒假也是绿，
# 所以合格面必须由这条自己写出一个该合格的对象。
_LEGIT_RESOLVER = """
def root() -> Path:
    env = os.environ.get("OMOSTATION_ROOT")
    if env and (Path(env) / MARKER).is_file():
        return Path(env)
    home = Path.home() / "Workspace"
    if (home / MARKER).is_file():
        return home
    raise RuntimeError("定位不到规范检出")
"""

# ── 钉住的实测现状 (bump 前跑 `.subtrees/omo` 得到的读数) ──────────────────

STATE_FAMILIES = frozenset(
    {
        ".omo/_delivery/alert-forwarder/watermark.json",
        ".omo/_delivery/event-ingest/watermark.json",
        ".omo/_delivery/observability/events.jsonl",
        ".omo/_delivery/perception-inbox/watermark.json",
        ".omo/_delivery/personal-signals/watermark.json",
        ".omo/_delivery/resident-orchestrator/daemon.log",
        ".omo/_delivery/resident-orchestrator/daemon.pid",
        ".omo/_delivery/resident-orchestrator/receipts.jsonl",
        ".omo/_delivery/resident-orchestrator/watermarks/*",
        ".omo/_knowledge",
        ".omo/_knowledge/bos-metrics.jsonl",
        ".omo/_knowledge/decision-proposals",
        ".omo/_knowledge/evolution-proposals",
        ".omo/_knowledge/omo-alerts.jsonl",
        ".omo/_knowledge/omo-events.jsonl",
        ".omo/_knowledge/omo-sync.jsonl",
        ".omo/_knowledge/omo-trail.jsonl",
        ".omo/_knowledge/retros/resident",
        ".omo/_knowledge/sediment",
        ".omo/_knowledge/sediment-archive",
        ".omo/_knowledge/workflow-mesh/events.jsonl",
        ".omo/_truth/task-center/dispatches",
        ".omo/state/*",
        ".omo/state/agent-cell-memory",
        ".omo/state/agent-cell-replay",
        ".omo/state/compute/dynamic_nodes.json",
        ".omo/state/compute/inference_metrics.json",
        ".omo/state/daemon/chat_session.json",
        ".omo/state/daemon/media",
        ".omo/state/daemon/resident.pid",
        ".omo/state/daemon/service_state.json",
        ".omo/state/memory/candidates",
        ".omo/state/memory/distilled_crystallization.json",
        ".omo/state/pipeline-supervisor-state.json",
        ".omo/state/refinement-snapshots",
        ".omo/state/refinements",
        ".omo/state/resident-heartbeat.jsonl",
        ".omo/state/resident-monitor.jsonl",
        ".omo/state/rule-vitality.jsonl",
        "runtime/cron",
        "runtime/cron/resident-daemon.log",
        "runtime/omo/event-ledger.sqlite3",
    }
)

# 经 resolver 但参数是另一处调用 → 静态扫不出族名；由
# test_default_db_path_consumers_are_anchored_at_call_time 单独钉。
OPAQUE_WRITERS = frozenset({"@OPAQUE:default_db_path"})

# resident/** 里**留在检出根**的写点。前四类不在本轮 22 个 write_surfaces 内 (台账
# circuit_breaker: 扩大面 → 停下登记)；execute.py 是判据-4 的协调面，永久留在检出。
# 2026-11-02: resident 侧状态面收敛 (cell_state / chat_engine / service_ctl 等) 使
# bare_inline 从 5 条 (4 个在册 + execute.py) 长到 16 条 —— 本表同步补全，否则「留在检出根」的写点会
# 静默多出而判据仍绿。
DEFERRED_RESIDENT_WRITERS = frozenset(
    {
        "resident/chat_engine.py",
        "resident/connectors_poll.py",
        "resident/escalate.py",
        "resident/inference_gateway.py",
        "resident/interact.py",
        "resident/memory_distiller.py",
        "resident/morning_briefing.py",
        "resident/night_patrol.py",
        "resident/notification.py",
        "resident/patrol.py",
        "resident/refine_rollback.py",
        "resident/screen_probe.py",
        "resident/sema_crystallizer.py",
        "resident/service_ctl.py",
        "resident/service_runner.py",
        "resident/swarm_custodian.py",
        "resident/task_queue.py",
    }
)
COORDINATION_PLANE_WRITERS = frozenset({"resident/execute.py"})

# 读侧 split 钉成集合相等。`SPLIT_ANCESTOR` 是同表的**严格祖先**那半。
# 类别 = 该 bin 文件里锚点的根: CHECKOUT=检出常量, CALLER=函数参数
# (由 CALLER_EVIDENCE 单独钉住), DERIVED=扫不出模块级定义 (归档面是死码; 活面出现时
# 由 test_derived_class_readers_are_archived_or_reviewed 逐条在册)。
#
# 2026-11-02: 补全 2026-10-10 起累积的口径缺口 —— omo 写面从 18 族长到 42 族
# (resident 状态面 + `_knowledge` jsonl 面)，本表与 CALLER_EVIDENCE 同步补齐。
# `.omo/_knowledge` 是**容器族** (11 个更具体的族是它的后代)，它的读者集就是那些
# 以 `_knowledge` 目录本身为根的读者 —— 逐条在册，不做「容器豁免」。
SPLIT_EXACT: dict[str, set[tuple[str, str]]] = {
    ".omo/_delivery/alert-forwarder/watermark.json": {
        ("bin/ssot/alert-forwarder.py", "CHECKOUT"),
    },
    ".omo/_delivery/event-ingest/watermark.json": {
        ("bin/ssot/event-ingest-adapter.py", "CHECKOUT"),
    },
    ".omo/_delivery/observability/events.jsonl": {
        ("bin/compass_radar.py", "CALLER"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
        ("bin/ssot/alert-forwarder.py", "CHECKOUT"),
        ("bin/ssot/observability-events.py", "CHECKOUT"),
    },
    ".omo/_knowledge": {
        ("bin/_archive/2026-08-25-dfsq-quota/subtraction-quota-enforcer.py", "CHECKOUT"),
        ("bin/_archive/2026-09-21-bin-quota-offset/real-scenario-runner.py", "DERIVED"),
        ("bin/_archive/alert-history.py", "CALLER"),
        ("bin/_archive/approve-proposal.py", "DERIVED"),
        ("bin/_archive/calibration-runner-v1.py", "CHECKOUT"),
        ("bin/_archive/cross-submodule-events.py", "CALLER"),
        ("bin/_archive/emergency-override.py", "CHECKOUT"),
        ("bin/_archive/graphify-local-extract.py", "CALLER"),
        ("bin/_archive/management-categorize.py", "CALLER"),
        ("bin/_archive/management-migrate.py", "CALLER"),
        ("bin/_archive/migrated_low_value/alert-history.py", "CALLER"),
        ("bin/_archive/migrated_low_value/cross-submodule-events.py", "CALLER"),
        ("bin/_archive/migrated_low_value/graphify-local-extract.py", "CALLER"),
        ("bin/_archive/migrated_low_value/state-stale-consume.py", "CHECKOUT"),
        ("bin/_archive/migrated_low_value/status-distribution.py", "CALLER"),
        ("bin/_archive/migrations/management-migrate.py", "CALLER"),
        ("bin/_archive/quota-clearance-2026-08-24/test_zones_check.py", "CHECKOUT"),
        ("bin/_archive/state-stale-consume.py", "CHECKOUT"),
        ("bin/_archive/status-distribution.py", "CALLER"),
        ("bin/_archive/swarm-manager.py", "CHECKOUT"),
        ("bin/adr/next-adr-id.py", "CHECKOUT"),
        ("bin/bc-os/north_star_meter_v2.py", "CALLER"),
        ("bin/bc-os/north_star_meter_v3.py", "CHECKOUT"),
        ("bin/bc-os/north_star_meter_v4.py", "CHECKOUT"),
        ("bin/bc-os/proposal-triage.py", "CHECKOUT"),
        ("bin/compass_radar.py", "CALLER"),
        ("bin/delivery/physical_recovery.py", "CHECKOUT"),
        ("bin/gac/adr-link-validator.py", "CHECKOUT"),
        ("bin/gac/anti-corrosion-detector.py", "CHECKOUT"),
        ("bin/gac/check-gateway-status-doc.py", "CHECKOUT"),
        ("bin/gac/check-resident-bos.py", "CHECKOUT"),
        ("bin/gac/check-work-landed.py", "CHECKOUT"),
        ("bin/gac/convergence-pulse.py", "CHECKOUT"),
        ("bin/gac/drift-sweep.py", "CHECKOUT"),
        ("bin/gac/error-knowledge.py", "CHECKOUT"),
        ("bin/gac/event-loop-lint.py", "CHECKOUT"),
        ("bin/gac/evidence-smoke.py", "CHECKOUT"),
        ("bin/gac/fix-frontmatter.py", "CALLER"),
        ("bin/gac/gac-validate.py", "CHECKOUT"),
        ("bin/gac/governance-convergence-lint.py", "CHECKOUT"),
        ("bin/gac/governance-readiness.py", "CALLER"),
        ("bin/gac/kos-seed-import.py", "CHECKOUT"),
        ("bin/gac/m1-closeout-report.py", "CALLER"),
        ("bin/gac/omostation-bootloader.py", "CHECKOUT"),
        ("bin/gac/p0-event-listener.py", "CALLER"),
        ("bin/gac/p78-diagnostic-prescan.py", "CHECKOUT"),
        ("bin/gac/retro-reference-engine.py", "CHECKOUT"),
        ("bin/gac/swarm_discipline.py", "CALLER"),
        ("bin/gac/value-evolution-connector.py", "DERIVED"),
        ("bin/kb/knowledge-graph.py", "CALLER"),
        ("bin/kb/staleness-check.py", "CALLER"),
        ("bin/mof/generate-brief.py", "CHECKOUT"),
        ("bin/mof/m4-health-score.py", "CHECKOUT"),
        ("bin/panorama/panel-collect.py", "CHECKOUT"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
        ("bin/plan/bet-closeout-auto.py", "CHECKOUT"),
        ("bin/plan/bet-ledger.py", "CHECKOUT"),
        ("bin/plan/chain-bind-audit.py", "CHECKOUT"),
        ("bin/reports/quarterly-report.py", "CHECKOUT"),
        ("bin/ssot/adr-number-check.py", "CALLER"),
        ("bin/ssot/dashboard.py", "CHECKOUT"),
        ("bin/ssot/decision-agent.py", "CHECKOUT"),
        ("bin/ssot/doc-lifecycle.py", "CHECKOUT"),
        ("bin/ssot/event-ingest-adapter.py", "CHECKOUT"),
        ("bin/ssot/evolution-agent.py", "CHECKOUT"),
        ("bin/ssot/gen-external-channels-inventory.py", "CHECKOUT"),
        ("bin/ssot/gen-knowledge-index.py", "CHECKOUT"),
        ("bin/ssot/governance-scanner.py", "CHECKOUT"),
        ("bin/ssot/journey-runner.py", "CHECKOUT"),
        ("bin/ssot/journey-state-store.py", "CALLER"),
        ("bin/ssot/knowledge-sediment.py", "CHECKOUT"),
        ("bin/ssot/mail_daemon.py", "CHECKOUT"),
        ("bin/ssot/management-categorize.py", "CALLER"),
        ("bin/ssot/management-cross-ref-check.py", "CALLER"),
        ("bin/ssot/mesh-consumer.py", "CHECKOUT"),
        ("bin/ssot/mos-dual-stack-consistency.py", "CHECKOUT"),
        ("bin/ssot/project_health_check.py", "CALLER"),
        ("bin/ssot/proposal-to-adr.py", "CHECKOUT"),
        ("bin/ssot/resident-orchestrator-daemon.py", "CHECKOUT"),
        ("bin/ssot/rule-adapt.py", "CHECKOUT"),
        ("bin/ssot/scene-batch-execute.py", "CHECKOUT"),
        ("bin/ssot/scene-card-lifecycle.py", "CALLER"),
        ("bin/ssot/scene-evolution-loop.py", "CHECKOUT"),
        ("bin/ssot/scene-feedback-collector.py", "CALLER"),
        ("bin/ssot/scene-graph.py", "CHECKOUT"),
        ("bin/ssot/scene-history.py", "CHECKOUT"),
        ("bin/ssot/scene-outcome-recorder.py", "CHECKOUT"),
        ("bin/ssot/scene-reflection.py", "CALLER"),
        ("bin/ssot/sema-distill.py", "CHECKOUT"),
        ("bin/ssot/sync-bos-registry.py", "CHECKOUT"),
        ("bin/ssot/system-health-check.py", "CHECKOUT"),
        ("bin/ssot/vision-audit.py", "CHECKOUT"),
        ("bin/sweep/scan.py", "CHECKOUT"),
        ("bin/sweep/sweep_index.py", "CHECKOUT"),
    },
    ".omo/_knowledge/decision-proposals": {
        ("bin/_archive/2026-09-21-bin-quota-offset/real-scenario-runner.py", "DERIVED"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
    },
    ".omo/_knowledge/evolution-proposals": {
        ("bin/_archive/2026-09-21-bin-quota-offset/real-scenario-runner.py", "DERIVED"),
        ("bin/_archive/approve-proposal.py", "DERIVED"),
        ("bin/bc-os/north_star_meter_v2.py", "CALLER"),
        ("bin/bc-os/proposal-triage.py", "CHECKOUT"),
        ("bin/ssot/decision-agent.py", "CHECKOUT"),
        ("bin/ssot/evolution-agent.py", "CHECKOUT"),
        ("bin/ssot/proposal-to-adr.py", "CHECKOUT"),
        ("bin/ssot/scene-evolution-loop.py", "CHECKOUT"),
    },
    ".omo/_knowledge/omo-events.jsonl": {
        ("bin/_archive/alert-history.py", "CALLER"),
        ("bin/_archive/cross-submodule-events.py", "CALLER"),
        ("bin/_archive/migrated_low_value/alert-history.py", "CALLER"),
        ("bin/_archive/migrated_low_value/cross-submodule-events.py", "CALLER"),
        ("bin/_archive/migrated_low_value/state-stale-consume.py", "CHECKOUT"),
        ("bin/_archive/state-stale-consume.py", "CHECKOUT"),
        ("bin/compass_radar.py", "CALLER"),
        ("bin/gac/event-loop-lint.py", "CHECKOUT"),
        ("bin/gac/evidence-smoke.py", "CHECKOUT"),
        ("bin/gac/p0-event-listener.py", "CALLER"),
    },
    ".omo/_knowledge/retros/resident": {
        ("bin/bc-os/north_star_meter_v2.py", "CALLER"),
    },
    ".omo/_knowledge/sediment": {
        ("bin/ssot/knowledge-sediment.py", "CHECKOUT"),
    },
    ".omo/_knowledge/workflow-mesh/events.jsonl": {
        ("bin/bc-os/north_star_meter_v3.py", "CHECKOUT"),
        ("bin/bc-os/north_star_meter_v4.py", "CHECKOUT"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
        ("bin/plan/bet-ledger.py", "CHECKOUT"),
        ("bin/ssot/event-ingest-adapter.py", "CHECKOUT"),
        ("bin/ssot/mail_daemon.py", "CHECKOUT"),
        ("bin/ssot/mesh-consumer.py", "CHECKOUT"),
        ("bin/ssot/resident-orchestrator-daemon.py", "CHECKOUT"),
        ("bin/ssot/system-health-check.py", "CHECKOUT"),
    },
    ".omo/_truth/task-center/dispatches": {
        ("bin/gac/check-test-host-hygiene.py", "CHECKOUT"),
    },
    ".omo/state/*": {
        ("bin/mof/m2-ssot-inventory.py", "CHECKOUT"),
    },
    ".omo/state/pipeline-supervisor-state.json": {
        ("bin/gac/convergence-pulse.py", "CHECKOUT"),
    },
    ".omo/state/rule-vitality.jsonl": {
        ("bin/gac/rule-vitality-tracker.py", "CHECKOUT"),
    },
    "runtime/cron": {
        ("bin/_archive/migrated_low_value/omo-doctor-cron.py", "CHECKOUT"),
        ("bin/_archive/omo-doctor-cron.py", "CHECKOUT"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
    },
    "runtime/omo/event-ledger.sqlite3": {
        ("bin/panorama/projection-full-refresh.py", "CALLER"),
    },
}

# 读点是族的**严格祖先目录** (log-rotate 清日志、p78 诊断预扫等)。
# log-rotate 是**目录级**清理者，它按祖先路径删日志 —— 写者改道而它没跟上
# 时，后果不是读不到而是**旧文件永不清理**，所以这一类比 exact 更必须钉住。
SPLIT_ANCESTOR: dict[str, set[tuple[str, str]]] = {
    ".omo/_delivery/event-ingest/watermark.json": {
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_delivery/perception-inbox/watermark.json": {
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_delivery/personal-signals/watermark.json": {
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_delivery/resident-orchestrator/daemon.log": {
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_delivery/resident-orchestrator/daemon.pid": {
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_delivery/resident-orchestrator/receipts.jsonl": {
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_delivery/resident-orchestrator/watermarks/*": {
        ("bin/gac/check-resident-status.py", "CALLER"),
        ("bin/gac/check-resident-status.py", "CHECKOUT"),
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_knowledge/retros/resident": {
        ("bin/gac/check-work-landed.py", "CHECKOUT"),
        ("bin/gac/fix-frontmatter.py", "CALLER"),
        ("bin/gac/p78-diagnostic-prescan.py", "CHECKOUT"),
        ("bin/gac/retro-reference-engine.py", "CHECKOUT"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
        ("bin/plan/bet-closeout-auto.py", "CHECKOUT"),
        ("bin/plan/bet-ledger.py", "CHECKOUT"),
        ("bin/plan/chain-bind-audit.py", "CHECKOUT"),
        ("bin/reports/quarterly-report.py", "CHECKOUT"),
    },
    ".omo/_knowledge/workflow-mesh/events.jsonl": {
        ("bin/ssot/scene-card-lifecycle.py", "CALLER"),
    },
}

# CALLER 类锚点 = 函数参数，静态类别未知。逐个把「谁传进来的、那位的根是什么」钉成
# 源码必须含有的**表达式**；`checkout=True` 时证据里必须出现检出锚点标记 —— 否则判据
# 退化成橡皮章。`checkout=False` 只允许一种情况: 根由**操作者**在命令行给出且无默认
# (fix-frontmatter)，那种读取点落在哪个根不是 omo 侧能决定的，也不构成本轮可修的 split。
CALLER_EVIDENCE: dict[tuple[str, str], dict[str, object]] = {
    # ws_root = args.omo_dir.resolve(); --omo-dir 默认 __file__ 反推 → 检出根
    ("bin/compass_radar.py", "ws_root"): {
        "exprs": ['default=Path(__file__).resolve().parent.parent / ".omo"', "omo_dir = args.omo_dir.resolve()"],
        "checkout": True,
    },
    # _knowledge_consumption(ROOT)，ROOT 是模块级检出常量
    ("bin/bc-os/north_star_meter_v2.py", "workspace_root"): {
        "exprs": ["_knowledge_consumption(ROOT)"],
        "checkout_via": "ROOT",
    },
    ("bin/ssot/scene-card-lifecycle.py", "root"): {
        "exprs": ['parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])'],
        "checkout": True,
    },
    ("bin/gac/fix-frontmatter.py", "root"): {
        "exprs": ["root = Path(args.batch)", 'parser.add_argument(\n        "--batch",\n        metavar="ROOT",'],
        "checkout": False,
    },
    # T10-247: ledger 根在**调用时刻**解析。读取点写成 `canonical_root() / "runtime" / ...`，
    # 静态类别是 CALLER（函数调用，扫不出模块级根定义），所以证据必须来自**那个 resolver 自己**。
    # 不用 `checkout: True`：它判的是 `exprs` 拼接文本里有没有 `__file__` / `parents[` / `code_root`
    # 子串 —— 而本文件第 43 行的 `sys.path.insert(... parents[1] ...)` 足以让任何 exprs 凑出标记，
    # 那是橡皮章。改由 `checkout_resolver` 拿 repo_root.py 的 AST 谓词作证（见 _violated_clauses）。
    ("bin/panorama/projection-full-refresh.py", "canonical_root"): {
        "exprs": [
            "from repo_root import canonical_root, state_root",
            'return canonical_root() / "runtime" / "omo" / "event-ledger.sqlite3"',
        ],
        "checkout_resolver": "canonical_root",
    },
    # 2026-11-02: `.omo/_knowledge` 一族带来的 25 个新 CALLER 锚点。
    ("bin/_archive/alert-history.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/cross-submodule-events.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/graphify-local-extract.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/management-categorize.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/management-migrate.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/migrated_low_value/alert-history.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/migrated_low_value/cross-submodule-events.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/migrated_low_value/graphify-local-extract.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/migrated_low_value/status-distribution.py", "root"): {
        "exprs": ["root = Path(sys.argv[1] if len(sys.argv) > 1 else \".\").resolve()"],
        "checkout": False,
    },
    ("bin/_archive/migrations/management-migrate.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/_archive/status-distribution.py", "root"): {
        "exprs": ["root = Path(sys.argv[1] if len(sys.argv) > 1 else \".\").resolve()"],
        "checkout": False,
    },
    ("bin/gac/check-resident-status.py", "base_root"): {
        "exprs": ["base_root = Path(root) if root else Path(REPO)"],
        "checkout": False,
    },
    ("bin/gac/governance-readiness.py", "root"): {
        "exprs": ["root = Path(sys.argv[1] if len(sys.argv) > 1 else \".\").resolve()"],
        "checkout": False,
    },
    ("bin/gac/m1-closeout-report.py", "base"): {
        "exprs": ["for base in (live, code_root):"],
        "checkout": False,
    },
    ("bin/gac/p0-event-listener.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/gac/swarm_discipline.py", "root"): {
        "exprs": ["root = Path(__file__).resolve().parents[2]"],
        "checkout": True,
    },
    ("bin/kb/knowledge-graph.py", "root"): {
        "exprs": ["build_graph(WORKSPACE)"],
        "checkout_via": "WORKSPACE",
    },
    ("bin/kb/staleness-check.py", "root"): {
        "exprs": [
            "scan_targets(WORKSPACE)",
            "check_file(WORKSPACE, f)",
        ],
        "checkout_via": "WORKSPACE",
    },
    ("bin/ssot/adr-number-check.py", "root"): {
        "exprs": ["root = Path(__file__).resolve().parents[2]"],
        "checkout": True,
    },
    ("bin/ssot/journey-state-store.py", "root"): {
        "exprs": ["parser.add_argument(\"--root\", type=Path, default=Path(__file__).resolve().parents[2])"],
        "checkout": True,
    },
    ("bin/ssot/management-categorize.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/ssot/management-cross-ref-check.py", "root"): {
        "exprs": [
            "parser.add_argument(\"root\", nargs=\"?\", default=\".\", help=\"workspace root\")",
            "root = Path(args.root).resolve()",
        ],
        "checkout": False,
    },
    ("bin/ssot/project_health_check.py", "root"): {
        "exprs": ["root = Path(__file__).resolve().parents[2] / args.project"],
        "checkout": True,
    },
    ("bin/ssot/scene-feedback-collector.py", "root"): {
        "exprs": ["parser.add_argument(\"--root\", type=Path, default=Path(__file__).resolve().parents[2])"],
        "checkout": True,
    },
    ("bin/ssot/scene-reflection.py", "root"): {
        "exprs": ["parser.add_argument(\"--root\", type=Path, default=Path(__file__).resolve().parents[2])"],
        "checkout": True,
    },
}

# 在册 STATE 读者评审集 —— 键**只有 rel**，不钉行号：`_state_readers` 返回 (rel, line) 对，
# 行号随该读者自身后续改动漂移 (T10-247 实测 line=58)，钉行号会让判据在无关改动当天假红。
# `rows` 钉的是**该文件里有几处调用时刻解析到 state 根的读取点**（一个文件可以有多处，
# 如 daemon 的三个访问器），所以计数不是恒 1；多一处未登记当场红。
REVIEWED_STATE_READERS = {
    "bin/panorama/projection-full-refresh.py": {
        "rows": 1,
        "why": "T10-247: ledger_db_path() 第②支 state_root() 落 profile 根",
    },
    "bin/ssot/resident-orchestrator-daemon.py": {
        "rows": 3,
        "why": "2026-10-29 读侧收敛: _pid_file / _log_file / _wm_path 三处调用时刻解析 state_root()",
    },
    "bin/ssot/system-health-check.py": {
        "rows": 1,
        "why": "2026-10-29 读侧收敛: _daemon_watermarks() 取代两级派生常量 (旧形状对检测器不可见)",
    },
}

# 已知**不对称** (不是 bug 清单的终点，是本轮登记): 台账 DB 覆盖名给了相对路径时，
# omo 侧 `.absolute()` 而 root 侧不 —— root 仓不在本轮 22 个 write_surfaces 内。
LEDGER_OVERRIDE_ASYMMETRY = "OMO_EVENT_LEDGER_DB 相对路径: repo_root 不 absolute, omo_paths 会"


# ── seams ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def omo_src() -> Path:
    return OMO_SRC


@pytest.fixture(scope="module")
def writers(omo_src):
    return scan_writers(omo_src)


@pytest.fixture(scope="module")
def measured(omo_src, writers):
    families = {f for f in writers["state"] if not f.startswith("@OPAQUE:")}
    rows = reader_pairs(BIN, families)
    return families, rows, _group(rows, "exact"), _group(rows, "ancestor")


def _run_ledger_probe(env: dict[str, str]) -> dict[str, str]:
    """在**子进程**里同时加载两仓的 resolver 并打印各自答案。

    必须子进程: `omo_paths.STATE_ROOT` 在 import 时求值，同进程换 env 测不到晚声明。
    """
    script = (
        "import importlib.util, json, sys\n"
        "def load(n, p):\n"
        "    s = importlib.util.spec_from_file_location(n, p)\n"
        "    m = importlib.util.module_from_spec(s); sys.modules[n] = m; s.loader.exec_module(m); return m\n"
        f"r = load('rr', {str(REPO_ROOT_PY)!r})\n"
        f"o = load('op', {str(OMO_PATHS_PY)!r})\n"
        "print(json.dumps({'repo': str(r.event_ledger_path()), 'omo': str(o.event_ledger_path())}))\n"
    )
    full = {k: v for k, v in os.environ.items() if k not in {"OMOSTATION_STATE_ROOT", "OMO_EVENT_LEDGER_DB"}}
    full.update(env)
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=full, check=True)
    return json.loads(out.stdout.strip())


# ── 检测器自证 (空绿 = 装置没命中，不是面收敛了) ──────────────────────────


def _synth_roots(tmp_path: Path, *, same_root: bool) -> tuple[Path, Path]:
    """一份合成小仓: 一个 resident 写者 + 一个 bin 读者，读同一族。"""
    omo = tmp_path / "src" / "omo"
    binp = tmp_path / "bin" / "ssot"
    omo.mkdir(parents=True)
    binp.mkdir(parents=True)
    (omo / "writer.py").write_text(
        "from pathlib import Path\n"
        "WORKSPACE = Path(__file__).resolve().parents[3]\n"
        'WATERMARK = WORKSPACE / ".omo" / "_delivery" / "x" / "watermark.json"\n'
        "def state_root():\n"
        "    return WORKSPACE\n"
        "def write_path(p):\n"
        "    return p\n"
        "def hit():\n"
        "    return write_path(WATERMARK)\n",
        encoding="utf-8",
    )
    reader_anchor = "state_root()" if same_root else "WORKSPACE"
    if same_root:
        reader_src = (
            "from pathlib import Path\n"
            "WORKSPACE = Path(__file__).resolve().parents[2]\n"
            "def state_root():\n"
            "    return WORKSPACE\n"
            "def read():\n"
            f"    return {reader_anchor} / '.omo' / '_delivery' / 'x' / 'watermark.json'\n"
        )
    else:
        reader_src = (
            "from pathlib import Path\n"
            "WORKSPACE = Path(__file__).resolve().parents[2]\n"
            "def read():\n"
            f"    return {reader_anchor} / '.omo' / '_delivery' / 'x' / 'watermark.json'\n"
        )
    (binp / "reader.py").write_text(reader_src, encoding="utf-8")
    return omo, binp


def test_detector_is_not_a_no_op(tmp_path):
    """合成 split 必须被点名 —— 否则「实测为空」只是装置没命中。"""
    omo, binp = _synth_roots(tmp_path, same_root=False)
    w = scan_writers(omo)
    fams = {f for f in w["state"] if not f.startswith("@OPAQUE:")}
    rows = reader_pairs(binp, fams)
    assert fams == {".omo/_delivery/x/watermark.json"}, fams
    assert len(rows) == 1
    fam, kind, rel, _line, anchor, klass = rows[0]
    assert (fam, kind, rel, anchor, klass) == (
        ".omo/_delivery/x/watermark.json",
        "exact",
        "ssot/reader.py",
        "WORKSPACE",
        "CHECKOUT",
    )
    assert _group(rows, "exact") == {".omo/_delivery/x/watermark.json": {("ssot/reader.py", "CHECKOUT")}}


def test_detector_does_not_flag_same_root_pair(tmp_path):
    """同根的一对不得进 split 清单 —— 只钉「有 split」的判据会把正常代码也报成违规。"""
    omo, binp = _synth_roots(tmp_path, same_root=True)
    w = scan_writers(omo)
    fams = {f for f in w["state"] if not f.startswith("@OPAQUE:")}
    rows = reader_pairs(binp, fams)
    assert [r[5] for r in rows] == ["STATE"], rows
    assert _group(rows, "exact") == {}


def test_nested_div_is_counted_once(tmp_path):
    """`a / b / c` 必须展平成**一条**路径；内层片段单独算会凭空多出族。"""
    tree = ast.parse('p = ROOT / ".omo" / "_delivery" / "x" / "watermark.json"')
    inner = _outermost_divs(tree)
    tops = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) and id(n) not in inner]
    assert len(tops) == 1
    assert _text(_chain(tops[0])[1:]) == ".omo/_delivery/x/watermark.json"


def test_order_of_chain_matches_source_order():
    """`ast.walk` 是 BFS: 用它拼片段会给出乱序族名，所以必须按源码顺序递归展平。"""
    tree = ast.parse('p = ROOT / "a" / "b" / "c"')
    top = next(n for n in ast.walk(tree) if isinstance(n, ast.BinOp))
    assert [_text([s]) for s in _chain(top)] == ["*", "a", "b", "c"]
    assert _text(_chain(top)) == "*/a/b/c"


# ── 写侧: 迁移集与「不许写半份」的边界 ───────────────────────────────────


def test_scan_loads_the_real_omo_surface(writers):
    """检测器必须在真实树上**命中东西**: 空 state 集 = 扫的不是迁移后的那份检出。"""
    assert set(writers["state"]) == set(STATE_FAMILIES)


def test_state_reached_families_are_the_declared_set(writers):
    got = {f for f in writers["state"] if not f.startswith("@OPAQUE:")}
    assert got == set(STATE_FAMILIES)


def test_opaque_resolver_args_are_the_declared_set(writers):
    assert set(writers["opaque"]) == set(OPAQUE_WRITERS)


def test_resident_inline_bare_writers_are_the_deferred_list(writers):
    """resident/** 里留在检出根的写点必须**逐文件在册**，不能靠「大概迁完了」。"""
    got = {
        rel for fam, hits in writers["bare_inline"].items() for rel, _line, _kind in hits if rel.startswith("resident/")
    }
    assert got == set(DEFERRED_RESIDENT_WRITERS) | set(COORDINATION_PLANE_WRITERS), got


def test_coordination_plane_stays_checkout_on_both_sides(writers, measured):
    """.omo/_delivery/agent-workflows/** 是全机共享面 (判据-4): 两侧都不得改道。"""
    fams, rows, _exact, _ancestor = measured
    assert not [f for f in fams if f.startswith(_COORDINATION)]
    assert not [r for r in rows if r[0].startswith(_COORDINATION)]
    got = {rel for fam, hits in writers["bare_inline"].items() if fam.startswith(_COORDINATION) for rel, _l, _k in hits}
    assert got == COORDINATION_PLANE_WRITERS | {"workflow/claims_authority.py"}, got


def test_registry_read_plane_is_never_state_reached(writers):
    """过度迁移的反向判据: 治理 SSOT (`.omo/_truth/registry/**`) 一旦被写进 state 族，
    读者 (跟着检出的那 40+ 处) 就读不到自己刚写的东西。"""
    fams = {f for f in writers["state"]} | {f for f in writers["bare_inline"]}
    registry_state = [f for f in writers["state"] if "_truth/registry" in f]
    assert registry_state == []
    assert any("_truth/registry" in f for f in fams)  # 判据不是空集自证


# ── 读侧: split 清单钉成集合相等 (双向) ──────────────────────────────────


def test_exact_root_split_pairs_are_the_reviewed_list(measured):
    _fams, _rows, exact, _an = measured
    assert exact == SPLIT_EXACT


def test_ancestor_root_split_pairs_are_the_reviewed_list(measured):
    _fams, _rows, _ex, ancestor = measured
    assert ancestor == SPLIT_ANCESTOR


def test_every_pinned_reader_names_a_real_file():
    for table in (SPLIT_EXACT, SPLIT_ANCESTOR):
        for fam, pairs in table.items():
            assert fam in STATE_FAMILIES, fam
            for rel, _klass in pairs:
                assert (ROOT / rel).is_file(), (fam, rel)


def test_bin_state_readers_are_the_reviewed_set(measured):
    """bin/ 侧的 STATE 读者**恰为在册那一组**，多一条未在册即红。

    改前（T10-233 基线）这条断言是 `_state_readers(rows) == []`，其含义是「bin/ 里没有任何读者
    解析到 state 根」，因而「读写同根」不可能靠改 omo 达成。T10-247 让 projection-full-refresh 的
    ledger 第②支落到 state 根，2026-10-29 又让 resident-orchestrator 一族的三个 bin 文件改到
    state 根，于是「零读者」这句**按事实不再成立** —— 用例随之改名并把否定式换成评审集，
    避免留着一条说谎的用例名。

    双向钉：① 实测 rel 集合 == REVIEWED_STATE_READERS 的键 (少了是读者消失，见
    test_ledger_family_has_a_single_root_contract_in_bin)；② 每个在册 rel 的**行数**等于登记的
    `rows` (一个文件可有多处访问器，daemon 实测 3 处)，所以「新增一处未登记的 STATE 读取」与
    「少了一处已登记的」都当场红。行号不进判据 (见 REVIEWED_STATE_READERS 注释)。
    """
    _fams, rows, _ex, _an = measured
    pairs = _state_readers(rows)
    rels = {rel for rel, _line in pairs}
    assert rels == set(REVIEWED_STATE_READERS), rels ^ set(REVIEWED_STATE_READERS)
    counts = {rel: sum(1 for r, _ in pairs if r == rel) for rel in rels}
    expect = {rel: spec["rows"] for rel, spec in REVIEWED_STATE_READERS.items()}
    assert counts == expect, (counts, expect)


def test_caller_class_anchors_are_checkout_anchored(measured):
    """CALLER = 静态未知，必须逐个用调用点表达式补证；无标记即视为未登记。"""
    _fams, rows, _ex, _an = measured
    seen = {(rel, anchor) for _f, _k, rel, _l, anchor, klass in rows if klass == "CALLER"}
    assert seen == set(CALLER_EVIDENCE), seen ^ set(CALLER_EVIDENCE)
    for (rel, _param), spec in CALLER_EVIDENCE.items():
        source = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        exprs = spec["exprs"]
        assert exprs, (rel, _param)
        for expr in exprs:
            assert expr in source, (rel, expr)
        if resolver := spec.get("checkout_resolver"):
            ok, violated, body = _checkout_anchored_resolver(resolver)
            assert ok, (rel, resolver, violated)
            assert body, (rel, resolver)
            assert f"{resolver}()" in source, (rel, resolver)
        elif via := spec.get("checkout_via"):
            assert _module_classes(ROOT / rel, {})[via] == "CHECKOUT", (rel, via)
        elif spec.get("checkout"):
            assert any(marker in " ".join(exprs) for marker in CHECKOUT_MARKERS), (rel, exprs)


def test_checkout_resolver_predicate_is_discriminating():
    """谓词的判别面: 通过集**恰为 {canonical_root}**，逐个拒绝指名条款，谓词非常真也非常假。

    名单不得手写：被检对象由 `repo_root.__all__` ∩ 模块级 def 导出 (AGENTS.md §7 ④ ——
    手写 resolver 名单有两处静默逃逸)。期望的拒绝理由由本轮实测填，改动 repo_root 后
    本用例红是**要求重算**，不是要求把期望改成新读数。
    """
    tree = _parse(REPO_ROOT_PY)
    assert tree is not None
    public = sorted(
        _all_names(tree)
        & {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    )
    assert public, "谓词失去被检对象"
    accepted = {n for n in public if _checkout_anchored_resolver(n)[0]}
    assert accepted == {"canonical_root"}, (sorted(accepted), public)

    expect = {
        "code_root": {"no-file-anchor", "refs-marker", "raises"},
        "state_root": {"refs-marker", "raises"},
        "event_ledger_path": {"no-state-marker", "refs-marker", "raises"},
        # install_root 按设计可返回 None（没有安装位的机器），④ 拒它不是它有误，
        # 而是「可能静默给 None」的定位器不能当检出根的证据。
        "install_root": {"raises"},
        "is_worktree": {"refs-marker", "raises", "zero-required-args"},
        "projection_name_for": {"refs-marker", "raises", "zero-required-args"},
        "projection_read": {"no-state-marker", "refs-marker", "raises", "zero-required-args"},
        # 三条判据草案的原通过集成员 —— 它是投影路径查询器，不是检出根定位器。
        "projection_rels": {"refs-marker", "zero-required-args"},
        "state_file_read": {"no-state-marker", "refs-marker", "raises", "zero-required-args"},
    }
    for name, want in expect.items():
        assert name in public, name
        ok, violated, _body = _checkout_anchored_resolver(name)
        assert not ok and set(violated) == want, (name, violated, want)


def test_checkout_resolver_predicate_names_each_synthetic_violation():
    """合成违规自证 (AGENTS.md §7 ②): 每Clause 单独破坏 → violated **恰为**那一条。"""
    legit = ast.parse(_LEGIT_RESOLVER).body[0]
    assert _violated_clauses(legit) == [], _violated_clauses(legit)

    bodies = {
        "no-file-anchor": _LEGIT_RESOLVER.replace(
            '    raise RuntimeError', '    base = Path(__file__).resolve().parents[2]\n    raise RuntimeError'
        ),
        "no-state-marker": _LEGIT_RESOLVER.replace(
            "    raise RuntimeError", "    return state_root()\n    raise RuntimeError"
        ),
        "refs-marker": _LEGIT_RESOLVER.replace(' / MARKER)', ' / "docs/project-registry.yaml")'),
        "raises": _LEGIT_RESOLVER.replace(
            '    raise RuntimeError("定位不到规范检出")', "    return None"
        ),
        "zero-required-args": _LEGIT_RESOLVER.replace(
            "def root() -> Path:", "def root(kind: str) -> Path:"
        ),
    }
    assert set(bodies) == set(_CHECKOUT_CLAUSES), set(bodies) ^ set(_CHECKOUT_CLAUSES)
    for clause, text in bodies.items():
        fn = ast.parse(text).body[0]
        assert _violated_clauses(fn) == [clause], (clause, _violated_clauses(fn))
    # 反向: 全破坏的体必须被五条同时指名（谓词不是「只报第一条」）
    everything = bodies["zero-required-args"].replace(
        ' / MARKER)', ' / "x")').replace('    raise RuntimeError("定位不到规范检出")', "    return None")
    assert set(_violated_clauses(ast.parse(everything).body[0])) == {
        "refs-marker", "raises", "zero-required-args"
    }, _violated_clauses(ast.parse(everything).body[0])


def test_checkout_resolver_evidence_mode_is_not_a_rubber_stamp():
    """`checkout_resolver` 不得被 `checkout: True` 替代：本文件的 parents[ 让子串判据恒过。

    这正是新增该模式的原因，所以把它钉成可测的事实而不是措辞。
    """
    rel, resolver = "bin/panorama/projection-full-refresh.py", "canonical_root"
    source = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    spec = CALLER_EVIDENCE[(rel, resolver)]
    assert "checkout" not in spec and spec.get("checkout_resolver") == resolver
    joined = " ".join(spec["exprs"])
    assert not any(marker in joined for marker in CHECKOUT_MARKERS), joined
    assert any(marker in source for marker in CHECKOUT_MARKERS), source


# DERIVED = 检测器扫不出模块级根定义。归档面那批是死码，不需要理由；**活面**出现时
# 必须逐条在册并写明为何静态不可判 —— 否则「未知根不得混进活面」会退化成一句空话，
# 而真正的回归（新增一个说不清根在哪的读者）反而没人看得见。
DERIVED_EVIDENCE: dict[str, str] = {
    "bin/gac/value-evolution-connector.py": (
        "REPO = _detect_repo(): 沿 Path(__file__).resolve().parents 上溯找 "
        "docs/project-registry.yaml，找不到回退 Path.cwd() —— 同一表达式有两个可能的根，"
        "静态不可判（它读的 .omo/_knowledge/facts/personal-preferences.jsonl 还带 "
        "OMO_PREFERENCES_LOG 环境覆盖）"
    ),
}


def test_derived_class_readers_are_archived_or_reviewed(measured):
    """DERIVED = 扫不出模块级根定义。归档面的那批是死码；**活面**出现时必须逐条在册。

    判据读**实测**表 (不是 `SPLIT_*` 字面量) —— 读字面量的话检测器退化了本用例也照样绿，
    那正是 AGENTS.md §7③ 的「按构造就绿」。双向钉：实测的活面 DERIVED 读者集合 == `DERIVED_EVIDENCE` 的键 —— 少了是有人
    把在册项「顺手删掉」, 多了是新增了一个说不清根在哪的读者, 两种都当场红。
    """
    _fams, _rows, exact, ancestor = measured
    live = set()
    for table in (exact, ancestor):
        for pairs in table.values():
            for rel, klass in pairs:
                if klass == "DERIVED" and not rel.startswith("bin/_archive/"):
                    live.add(rel)
    assert live == set(DERIVED_EVIDENCE), live ^ set(DERIVED_EVIDENCE)
    for rel, why in DERIVED_EVIDENCE.items():
        assert (ROOT / rel).is_file(), rel
        assert why, rel


def test_ledger_family_has_a_single_root_contract_in_bin():
    """台账族的 bin 读者必须同一口径，否则「谁读到哪份 ledger」取决于调用者。

    静态可见的 split 读者**恰为** projection-full-refresh (T10-247 起它的 ledger 第②支
    落 state 根)。#5014 把 `panorama-collect.py` 的 ledger 解析也改到**调用时刻**
    (`event_ledger_path()`) —— resolver 无实参, 检测器的路径表达式判据看不见它, 于是它
    既不进本表也不该进：它已经与写者同根。所以这里**两条都钉** —— 只钉前者的话,
    把那一行删掉、让采集器退回检出根, 本表照样绿。
    """
    _fams, _rows, exact, _an = ledger_measured()
    readers = {rel for rel, _k in exact.get("runtime/omo/event-ledger.sqlite3", set())}
    assert readers == {"bin/panorama/projection-full-refresh.py"}, readers
    source = (ROOT / "bin/panorama/panorama-collect.py").read_text(encoding="utf-8", errors="ignore")
    assert "event_ledger_path()" in source, "采集器不再调用时刻解析 ledger 根"
    assert "runtime/omo/event-ledger" not in source, "采集器退回了检出根字面量"


def ledger_measured():
    w = scan_writers(OMO_PATHS_PY.parent)
    fams = {f for f in w["state"] if not f.startswith("@OPAQUE:")}
    rows = reader_pairs(BIN, fams | {"runtime/omo/event-ledger.sqlite3"})
    return fams, rows, _group(rows, "exact"), _group(rows, "ancestor")


# ── 两仓同一 ledger 口径: 靠执行，不靠措辞 ───────────────────────────────


def test_both_repositories_answer_the_ledger_path_identically(tmp_path):
    configs = [
        ({}, "未声明 profile"),
        ({"OMOSTATION_STATE_ROOT": str(tmp_path / "state")}, "声明 state 根"),
        ({"OMO_EVENT_LEDGER_DB": str(tmp_path / "abs.sqlite3")}, "绝对路径覆盖"),
    ]
    for env, why in configs:
        got = _run_ledger_probe(env)
        assert got["repo"] == got["omo"], (why, got)
    expect = len(configs)
    got_n = len(configs)
    print(f"expect={expect} got={got_n}")


def test_relative_ledger_override_divergence_is_registered(tmp_path):
    """已知不对称的**正向**登记: 相对覆盖名两仓答案不同 (repo 保留相对, omo absolute)。

    修它要动 `bin/lib/repo_root.py` —— 不在本轮 22 个 write_surfaces，所以钉成现状。
    """
    rel = "relative-name.sqlite3"
    got = _run_ledger_probe({"OMO_EVENT_LEDGER_DB": rel})
    assert got["repo"] == rel
    assert got["omo"] != rel, LEDGER_OVERRIDE_ASYMMETRY


def test_omo_checkout_carries_the_write_plane_mechanism(omo_src):
    """反向保护: 若有人**没** bump gitlink 就指望本文件为绿，这里先红并指名原因。"""
    source = (omo_src / "resident" / "__init__.py").read_text(encoding="utf-8")
    assert "def write_path(" in source, (
        f"{omo_src} 还是迁移前的检出: 先 bump-pointer 再 "
        "`git submodule update --init projects/omo`；开发期请用 OMO_RESIDENT_SRC 指向 .subtrees/omo"
    )


# ── 队列 DB 家族: 静态看不见的那一半 ────────────────────────────────────


def test_default_db_path_consumers_are_anchored_at_call_time(omo_src):
    """`write_path(default_db_path())` 对检测器是 @OPAQUE，所以这里按**调用点**钉。

    规则: `default_db_path()` 的每个 resident 消费者都必须重新锚定，唯一例外是它的宿主
    `task_queue.py` 自己的 CLI 默认值 (deferred 在册)。少包一处 = daemon 写 state 根、
    CLI 写检出 —— 正是本轮要防的 evidence-smoke SPLIT 形状。
    """
    hits = []
    for path in sorted((omo_src / "resident").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "default_db_path()" not in text:
            continue
        for line in text.splitlines():
            if "default_db_path()" not in line:
                continue
            if line.lstrip().startswith(("def ", '"', "#")):
                continue
            hits.append((path.name, line.strip()))
    wrapped = {(name, ln) for name, ln in hits if "write_path(default_db_path())" in ln}
    host = {(name, ln) for name, ln in hits if name == "task_queue.py"}
    assert wrapped | host == set(hits), sorted(set(hits) - wrapped - host)
    assert {name for name, _ in wrapped} == {"daemon.py", "decision.py", "sediment.py"}, sorted(wrapped)


# ── RELATIVE 类目用例 (BET-Y2Q4-T10-288, spec §5 AC-01) ────────────────────

RULER_B = ROOT / "tests" / "unit" / "test_writeplane_root_pin.py"

# 登记单位是 `(文件, 展平后的相对根)`，与尺 B 的 `BASELINE_RELATIVE_SITES` 同构：还掉一处就同时
# 删这一行并改那个脚本，只减不增。键口径 = 仓库相对路径（尺 B 同口径，便于两把尺对拍）。
# 2026-11-06 还掉 `bin/notification.py` 的两处：提案面改 env 缺席即拒写、配置读面改 `_config_path()`
# 经 `code_root()`（spec §5 AC-02）。差额判据见 `test_two_rulers_agree_on_the_relative_face`。
RELATIVE_REGISTER: dict[tuple[str, str], str] = {
    ("projects/omo/src/omo/workflow/lock_graph.py", ".omo/state"): (
        "spec §2 站点①：`:5 STATE_DIR = Path(\".omo\")` → `:10 state_dir` → mkdir/write_text，"
        "写面 = `<CWD>/.omo/state/lock-graph.json`。T10-288 裁为**显式降级 + 登记**（今天无生产者，"
        "只把 `:5` 换成缝是化妆式修复）；删代码需另行授权，见 ADR-0456 addendum"
    ),
    ("bin/gac/gate-roi-report.py", ".omo/_knowledge/governance-history.jsonl"): "只读（`load_events(HISTORY)`），未声明根 ⇒ 不同 CWD 读到不同历史面",
    ("bin/hitl-proposal.py", ".omo/_knowledge/hitl-proposals"): (
        "HITL 提案面的**生产者**（`create_proposal`/`_save_proposal` 写）。T10-288 只裁了消费者 "
        "`bin/notification.py`（env 缺席即拒写），生产者仍随 CWD —— 两半必须同一次交付改，否则读写分叉比现状更坏"
    ),
    ("bin/ops/continual-harness-refine.py", ".omo/_knowledge/skills"): "写面（`_emit_skills` mkdir 后逐个 skill 落盘）",
    ("bin/ops/continual-harness-refine.py", ".omo/_knowledge/refinements"): "写面（`run_refine` 里 mkdir 后写 receipt）",
    ("bin/ssot/auto-bump-doc-governance-budget.py", ".omo/_truth/registry/document-governance.yaml"): (
        "写治理 SSOT registry（`bump_budget`）—— 随 CWD 意味着在 worktree 里跑就改那份检出"
    ),
    ("bin/ssot/fm_schema_migrate.py", ".omo/_knowledge"): "`main` 里拿它当 `rglob('*.md')` 的遍历根，迁移后回写 frontmatter",
    ("bin/gac/check-debt-closure-discipline.py", ".omo/debt/items"): (
        "读 `.omo/debt/items` 面（`scan_gate_level_enum(Path(\".omo/debt/items\"))`，形参在 callee 里被当遍历根）。"
        "尺 B 不登记这一条，因为它的 `ALL_MARKERS` 不含 `.omo/debt` —— 见 `test_two_rulers_agree_on_the_relative_face` "
        "的标记边界差量"
    ),
}

# 两把尺在 bin 面的**声明差额**：尺 B 只登记 `ALL_MARKERS` 命中的根，`.omo/debt` 不在其中，
# 所以这一条只有尺 A 看得见。它是标记边界的产物，不是判据分歧 —— 多出第二处即说明两把尺真的分叉了。
RULER_B_MARKER_BLIND = frozenset({("bin/gac/check-debt-closure-discipline.py", ".omo/debt/items")})

_REL_B_CHAIN = (
    "from pathlib import Path\n"
    "STATE_DIR = Path('.omo')\n"
    "def emit(out):\n"
    "    state_dir = STATE_DIR / 'state'\n"
    "    state_dir.mkdir(parents=True, exist_ok=True)\n"
    "    (state_dir / 'lock-graph.json').write_text(out)\n"
)
_REL_B_CALL = (
    "import os\n"
    "from pathlib import Path\n"
    "D = Path(os.environ.get('SOME_UNDECLARED_DIR', '.omo/_knowledge/hitl-proposals'))\n"
    "D.mkdir(parents=True, exist_ok=True)\n"
)


def _write_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    src = tmp_path / "src"
    for rel, text in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return src


def test_relative_category_hits_shape_a_on_the_omo_write_plane(writers):
    """spec §2 站点① 在真实 omo 树上必须是**活的读数**，而不是只在合成树上演示。

    同一处站点原先四个桶全部不命中（`reader_pairs:325`/`scan_writers:551` 的 `_text(segs[1:])`
    把锚丢掉后比较串是 `state/…`，过不了 `_repo_path`），所以「只进 relative」这一句本身就是
    「第四类根此前按构造不可见」的反证 —— 若有人把 relative 并进 state/bare_*，这条会因
    第二个断言而红，而不是静默换个桶。
    """
    got = writers["relative"]
    assert ".omo/state" in got, sorted(got)
    assert ("workflow/lock_graph.py", 23, "chain") in got[".omo/state"], got[".omo/state"]
    for bucket in ("state", "bare_template", "bare_inline", "opaque"):
        hits = {(rel, line) for fam in writers[bucket].values() for rel, line, _k in fam}
        assert not [rel for rel, _ in hits if rel == "workflow/lock_graph.py"], bucket


def test_relative_register_is_the_reviewed_list():
    """两棵真实树的站点**逐条在册**，双向钉：多一处未登记即红，少一处（还掉了却没删登记）也红。"""
    omo_tail = "projects/omo/src/omo" if ".subtrees" in OMO_SRC.as_posix() else OMO_SRC.relative_to(ROOT).as_posix()
    rows: set[tuple[str, str]] = set()
    for fam, hits in scan_relative_writers(OMO_SRC).items():
        for rel, _line, _shape in hits:
            rows.add((f"{omo_tail}/{rel}", fam))
    for fam, hits in scan_relative_writers(BIN).items():
        for rel, _line, _shape in hits:
            rows.add((f"bin/{rel}", fam))
    assert rows == set(RELATIVE_REGISTER), rows ^ set(RELATIVE_REGISTER)


def test_relative_detector_fires_on_both_shapes(tmp_path):
    """正面：AC-01 两形各一（派生链 / 单 `Path()` 调用带仓内相对默认）。"""
    chain = _write_tree(tmp_path / "a", {"m_chain.py": _REL_B_CHAIN})
    call = _write_tree(tmp_path / "b", {"m_call.py": _REL_B_CALL})
    got_chain = scan_relative_writers(chain)
    got_call = scan_relative_writers(call)
    assert {f for f in got_chain if f.startswith(".omo/state")} == {".omo/state"}, sorted(got_chain)
    assert got_chain[".omo/state"][0][2] == "chain", got_chain
    assert ".omo/_knowledge/hitl-proposals" in got_call, sorted(got_call)
    assert got_call[".omo/_knowledge/hitl-proposals"][0][2] == "call", got_call


def test_relative_detector_does_not_fire_on_seam_checkout_or_suffix(tmp_path):
    """反面：缝 / 检出根 / 后缀片段 / 形参进来的根 / env 无相对默认 —— 都不是第四类根。

    第 2 条是本轮最有价值的一条：`LEDGER_RELATIVE = Path("runtime/omo/event-ledger.sqlite3")`
    按值形状命中 AC-01(b)，但它被 `state_root() / LEDGER_RELATIVE` 当**后缀**用，落点由 state 根
    决定。按值判（而不是按用法判）会把这一形判成 CWD 根 —— 本轮实测 bin/ 侧有 33 个这样的值形状，
    绝大多数不是根，这正是 `_classify` 里不加 RELATIVE 分支的原因。
    """
    src = _write_tree(
        tmp_path,
        {
            "seam.py": (
                "from pathlib import Path\n"
                "def state_root(): return Path('/tmp/state')\n"
                "p = state_root() / '.omo/state/x.json'\n"
                "p.write_text('{}')\n"
            ),
            "checkout.py": (
                "from pathlib import Path\n"
                "W = Path(__file__).resolve().parents[2]\n"
                "p = W / '.omo/state/x.json'\n"
                "p.write_text('{}')\n"
            ),
            "suffix.py": (
                "from pathlib import Path\n"
                "LEDGER_RELATIVE = Path('runtime/omo/event-ledger.sqlite3')\n"
                "def state_root(): return Path('/tmp/state')\n"
                "p = state_root() / LEDGER_RELATIVE\n"
                "p.parent.mkdir(parents=True, exist_ok=True)\n"
            ),
            "param.py": (
                "from pathlib import Path\n"
                "def emit(base):\n"
                "    p = base / '.omo/state/x.json'\n"
                "    p.write_text('{}')\n"
                "emit(Path('/tmp/elsewhere'))\n"
            ),
            "env_abs.py": (
                "import os\n"
                "from pathlib import Path\n"
                "D = Path(os.environ.get('SOME_DIR', '/var/tmp/elsewhere'))\n"
                "(D / 'x').mkdir()\n"
            ),
            "env_bare.py": "import os\nfrom pathlib import Path\nD = Path(os.environ.get('SOME_DIR'))\n(D / 'x').mkdir()\n",
        },
    )
    got = scan_relative_writers(src)
    assert got == {}, {fam: hits for fam, hits in got.items()}


def test_classifier_does_not_claim_a_root_for_relative_fragments():
    """`_classify` 不新增 RELATIVE 分支，是裁决而不是遗漏 —— 钉住它，防止下一轮「补全类目」把它补错。

    该函数只拿得到值表达式，拿不到用法，所以按值判必然把 `LEDGER_RELATIVE` 这类后缀片段判成
    CWD 根；且读侧 223 行里锚点是仓内相对量的为 0 行，加了也是永不发火的装饰。
    """
    assert _classify(ast.parse("Path('runtime/omo/event-ledger.sqlite3')").body[0].value) == "DERIVED"
    assert _classify(ast.parse("Path(os.environ.get('X', '.omo/_knowledge/x'))").body[0].value) == "EXTERNAL"


def test_relative_category_is_load_bearing(tmp_path):
    """变异对照：摘掉一形 ⇒ 该形读数归零；两形全摘 ⇒ 空，而真实树非空 ⇒ 「绿」不是装置没命中。"""
    both = _write_tree(tmp_path, {"m.py": _REL_B_CHAIN + "\n" + _REL_B_CALL})
    chain_only = scan_relative_writers(both, ("chain",))
    call_only = scan_relative_writers(both, ("call",))
    off = scan_relative_writers(both, ())
    assert set(chain_only) == {".omo/state"}, sorted(chain_only)
    assert set(call_only) == {".omo/_knowledge/hitl-proposals"}, sorted(call_only)
    assert off == {}, off
    assert scan_relative_writers(OMO_SRC), "真实 omo 树读数为空 ⇒ 类目退化成了不可见"
    assert scan_relative_writers(BIN), "真实 bin 树读数为空 ⇒ 类目退化成了不可见"


def test_two_rulers_agree_on_the_relative_face():
    """两把尺的第四类根在 **bin 面**必须对得上：尺 B 的读数 ⊆ 尺 A 的读数，差额只能是有界的那一条。

    判据同源靠对拍保证，不靠「两边都照抄 spec」—— 抄两遍而不对拍，就是 §7「检测器的分类规则要
    与标记清单同源」的下一个事故。差额是**声明集合**（尺 A 侧的登记面含 omo 树，尺 B 只扫 bin/，
    所以这里比的是 bin 面）：`.omo/debt` 不在尺 B 的 `ALL_MARKERS` 里，那一条尺 B 结构性看不见
    （本轮实测），不是尺 A 多判。反向差额（尺 B 有、尺 A 无）由 `b_keys <= a_keys` 直接堵死 ——
    两把尺同源函数名，出现反向差额说明有一把的匹配规则退化。
    """
    spec_ = importlib.util.spec_from_file_location("t288_ruler_b_under_test", RULER_B)
    assert spec_ is not None and spec_.loader is not None
    ruler_b = importlib.util.module_from_spec(spec_)
    sys.modules["t288_ruler_b_under_test"] = ruler_b
    try:
        spec_.loader.exec_module(ruler_b)
        b_keys = {(f, fam) for f, _ln, _m, fam in ruler_b.scan_cwd_relative_sites(ROOT)}
    finally:
        sys.modules.pop("t288_ruler_b_under_test", None)
    a_keys = {(f"bin/{rel}", fam) for fam, hits in scan_relative_writers(BIN).items() for rel, _l, _s in hits}
    assert b_keys <= a_keys, b_keys - a_keys
    assert a_keys - b_keys == RULER_B_MARKER_BLIND, a_keys ^ (b_keys | RULER_B_MARKER_BLIND)


# ── AC-05 的用测（登记双向 + 合成正反 + 容器不覆盖后代 + 适用范围） ─────────────
#
# 登记表 = 「有 state 根锚、族表未登记」的面。键是平面，值是具名理由（哪一处锚、该谁收口）。
# 规则与 `SPLIT_EXACT` 那批允许清单同构：**只减不增**，且双向相等 —— 新面出现 ⇒ 红；面已经
# 登记进族表却还留在这里 ⇒ 也红（否则这条尺会变成一份追不上代码的名单，§7「检测器的分类规则要
# 与标记清单同源」的反面）。

UNREGISTERED_STATE_ROOT_PLANES = {
    ".omo/_knowledge/workflow-mesh/journey-states": (
        "omo_agent_host.py 的 `root_state`（:483/:581）挂在 state 根上读这个面，族表只有容器和 "
        "`workflow-mesh/events.jsonl`。spec §5 点名的就是这一条 —— 收口方式二选一：登记成族，"
        "或把锚改回具名跟踪面。"
    ),
    ".omo/debt/gap-items": (
        "omo_agent_host.py:615 同一个表达式里两个根（:612 `root_code` 读已跟踪的 `debt/items`、"
        ":615 `root_state` 读未跟踪的 `debt/gap-items`，BET-Y2Q4-T10-239 的按 trackedness 分根）。"
        "`debt` 整支不在本 BET 的扫描面（`.omo/_knowledge` 桶）里，所以这里点名而不在 289 内裁定。"
    ),
}


def test_state_root_planes_without_family_are_the_reviewed_gaps():
    measured = state_root_planes_without_family(OMO_SRC)
    assert set(measured) == set(UNREGISTERED_STATE_ROOT_PLANES), (
        f"新增未登记的 state 根面: {sorted(set(measured) - set(UNREGISTERED_STATE_ROOT_PLANES))} / "
        f"已闭合却仍挂名单: {sorted(set(UNREGISTERED_STATE_ROOT_PLANES) - set(measured))}"
    )
    assert all(reason.strip() for reason in UNREGISTERED_STATE_ROOT_PLANES.values())


def test_family_closure_detector_fires_on_gap_not_on_registered_or_checkout(tmp_path):
    """合成正反：只有点名得中「state 根 + 未登记面」这一组合才算数。"""
    src = tmp_path / "omo"
    src.mkdir(parents=True)
    (src / "gap.py").write_text(
        "from pathlib import Path\n\n"
        "def state_root() -> Path:\n"
        "    return Path('/tmp/state')\n\n"
        "def code_root() -> Path:\n"
        "    return Path('/tmp/checkout')\n\n"
        "def run() -> None:\n"
        "    root_state = state_root()\n"
        '    list((root_state / ".omo" / "_knowledge" / "brand-new-plane").glob("*.json"))\n'
        '    list((root_state / ".omo" / "_knowledge" / "sediment" / "x").glob("*.json"))\n'
        "    root_code = code_root()  # 检出根锚点：同一个面挂 code 根是契约不是缺口\n"
        '    list((root_code / ".omo" / "_knowledge" / "another-new").glob("*.json"))\n',
        encoding="utf-8",
    )
    named = state_root_planes_without_family(src)
    assert ".omo/_knowledge/brand-new-plane" in named, named
    assert ".omo/_knowledge/sediment/x" not in named, named  # 已登记族的后代
    assert ".omo/_knowledge/another-new" not in named, named  # 锚点是检出根，不是 state 根
    # 反「按构造就绿」：第三处必须**进到待判桶里**，被排除靠的是锚点判据而不是没被扫到。
    assert ".omo/_knowledge/another-new" in scan_writers(src)["bare_inline"], (
        "该站点没进 bare_inline 桶 ⇒ 上面那条 not-in 是按构造成立，锚点判据不被承重"
    )


def test_container_family_covers_itself_but_not_its_descendants():
    """AC-05 与尺 B 的 AC-02 同一条错误的两面：容器族不得替后代声明「已登记」。"""
    assert _family_covers(".omo/_knowledge") == ".omo/_knowledge"
    assert _family_covers(".omo/_knowledge/decisions") is None
    assert _family_covers(".omo/_knowledge/sediment/runs") == ".omo/_knowledge/sediment"
    assert _family_covers(".omo/state/whatever/deep.json") == ".omo/state/*"
    assert _family_covers(".omo/_knowledge/workflow-mesh/events.jsonl") == (
        ".omo/_knowledge/workflow-mesh/events.jsonl"
    )


def test_family_table_is_declared_not_closed_over_the_scanned_bucket():
    """适用范围（spec §7 AC-05 末句）：裁的是 `.omo/_knowledge` 桶这 62 站点，不是族表全量。

    这条用例是那句声明的**可跑版本**：尺 B 的分桶里 `NOT_DECLARED` 必须仍然非零。若哪天它归零
    （族表补全或桶改名），说明适用范围变了，本条连同 ADR-0456 addendum 的适用范围那句一起改，
    不许静默留下一个永不发火的分支。
    """
    spec_ = importlib.util.spec_from_file_location("t289_ruler_b_for_closure", RULER_B)
    assert spec_ is not None and spec_.loader is not None
    ruler_b = importlib.util.module_from_spec(spec_)
    sys.modules["t289_ruler_b_for_closure"] = ruler_b
    try:
        spec_.loader.exec_module(ruler_b)
        buckets = ruler_b.knowledge_bucket(ruler_b.scan_checkout_pinned_sites(ROOT))
    finally:
        sys.modules.pop("t289_ruler_b_for_closure", None)
    assert len(buckets["NOT_DECLARED"]) == 44, len(buckets["NOT_DECLARED"])
    assert len(buckets["SPECIFIC_FAMILY"]) == 13
    unregistered_in_bucket = {
        s[3] for s in buckets["NOT_DECLARED"] if _family_covers(s[3]) is None
    }
    assert unregistered_in_bucket, "44 个未登记面全部被族表覆盖了 —— 适用范围那句要重写"
