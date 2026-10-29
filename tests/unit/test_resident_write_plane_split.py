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

⚠️ 现状 (三次移动: T10-233 初判 → T10-247 → 2026-10-29 bin/ 读侧收敛): T10-233 基线上 bin/ 侧**没有
任何读者**解析到 state 根 (类别只有 CHECKOUT / CALLER / DERIVED)，因此「读写同根」在不动 `bin/` 的
前提下**结构上不可能达成**；台账 circuit_breaker 明确「需要改 bin/ 读者 → 停下登记而不是扩大 PR」，
所以当时这里是登记，不是豁免的省略。T10-247 把 projection-full-refresh 的 ledger 第②支落到 state 根，
2026-10-29 把 `.omo/_delivery/resident-orchestrator/**` 一族两个文件里的四处访问器 (`_pid_file` /
`_log_file` / `_wm_path` / `_daemon_watermarks`) 改为调用时刻解析 —— 于是
「零读者」这句**按事实不再成立**，读侧改为钉 `REVIEWED_STATE_READERS` 评审集 (含每个在册文件的
STATE 行数)。
**本族已读写同根**；其余族 (workflow-mesh events、observability、retros/resident、event-ingest 等)
仍是**已登记的 split 现状**，`log-rotate.py` 按设计留在检出根并由
`tests/unit/test_resident_plane_readers_state_root.py::test_log_rotate_stays_registered` 钉住 ——
它清的是祖先目录，漏改的后果不是读不到而是旧文件永不清理。

开发期读的是 `projects/omo` (分支 gitlink 的检出)；未 bump-pointer 时那份还没有写面机制，
`test_omo_checkout_carries_the_write_plane_mechanism` 会当场红并指名原因。用
`OMO_RESIDENT_SRC` 指向 `.subtrees/omo/src/omo` 可在 bump 之前跑同一份判据。
"""

from __future__ import annotations

import ast
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
    d = ast.dump(value)
    if any(k in d for k in _STATE_MARKERS):
        return "STATE"
    if "parents[" in d or "__file__" in d:
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
    """模块级 `NAME = <expr>` 的根类别，含一跳 sibling import (`from _shared import ROOT`)。"""
    if path in cache:
        return cache[path]
    cache[path] = {}
    tree = _parse(path)
    if tree is None:
        return cache[path]
    cls: dict[str, str] = {}
    imported: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and node.value is not None:
                    cls[t.id] = _classify(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            cls[node.target.id] = _classify(node.value)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                imported[a.asname or a.name] = node.module
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


def scan_writers(src: Path) -> dict[str, dict[str, list[tuple[str, int, str]]]]:
    """src/**.py → {bucket: {family: [(file, line, kind)]}}, bucket ∈ state|bare_template|bare_inline|opaque。"""
    buckets: dict[str, dict[str, list[tuple[str, int, str]]]] = {
        "state": {},
        "bare_template": {},
        "bare_inline": {},
        "opaque": {},
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
    return buckets


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
        ".omo/_knowledge/decision-proposals",
        ".omo/_knowledge/evolution-proposals",
        ".omo/_knowledge/retros/resident",
        ".omo/_knowledge/sediment",
        ".omo/_knowledge/sediment-archive",
        ".omo/_knowledge/workflow-mesh/events.jsonl",
        ".omo/state/resident-heartbeat.jsonl",
        ".omo/state/resident-monitor.jsonl",
        "runtime/omo/event-ledger.sqlite3",
    }
)

# 经 resolver 但参数是另一处调用 → 静态扫不出族名；由
# test_default_db_path_consumers_are_anchored_at_call_time 单独钉。
OPAQUE_WRITERS = frozenset({"@OPAQUE:default_db_path"})

# resident/** 里**留在检出根**的写点。前四类不在本轮 22 个 write_surfaces 内 (台账
# circuit_breaker: 扩大面 → 停下登记)；execute.py 是判据-4 的协调面，永久留在检出。
DEFERRED_RESIDENT_WRITERS = frozenset(
    {
        "resident/connectors_poll.py",
        "resident/sema_crystallizer.py",
        "resident/swarm_custodian.py",
        "resident/task_queue.py",
    }
)
COORDINATION_PLANE_WRITERS = frozenset({"resident/execute.py"})

# 9 个族 / 30 对 (T10-233 基线为 12 族 / 33 对；resident-orchestrator 的 daemon.log / daemon.pid /
# watermarks 三行随 2026-10-29 读者改道移出，判据是集合相等，所以改道后**必须**同步删表)。
# 类别 = 该 bin 文件里锚点的根: CHECKOUT=检出常量, CALLER=函数参数
# (由 CALLER_EVIDENCE 单独钉住), DERIVED=扫不出模块级定义 (只出现在归档/死码里)。
SPLIT_EXACT: dict[str, set[tuple[str, str]]] = {
    ".omo/_delivery/alert-forwarder/watermark.json": {
        ("bin/ssot/alert-forwarder.py", "CHECKOUT"),
    },
    ".omo/_delivery/event-ingest/watermark.json": {
        ("bin/ssot/event-ingest-adapter.py", "CHECKOUT"),
    },
    ".omo/_delivery/observability/events.jsonl": {
        ("bin/compass_radar.py", "CALLER"),
        ("bin/meta/compass_radar.py", "CALLER"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
        ("bin/ssot/alert-forwarder.py", "CHECKOUT"),
        ("bin/ssot/observability-events.py", "CHECKOUT"),
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
    "runtime/omo/event-ledger.sqlite3": {
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
        ("bin/panorama/projection-full-refresh.py", "CALLER"),
    },
}

# 9 个族 / 17 对 (与 T10-233 基线同数：check-resident-status **仍是**检出根读者 —— 它是 sgf-policy 登记
# 的 gate 脚本，落 governance_code lane，与本 code lane 腿不能同批交付，见
# `tests/unit/test_resident_plane_readers_state_root.py::test_check_resident_status_still_registered_checkout`)。
# log-rotate 是**目录级**清理者，它按祖先路径删日志 —— 写者改道而它没跟上
# 时，后果不是读不到而是**旧文件永不清理**，所以这一类比 exact 更必须钉住。
SPLIT_ANCESTOR: dict[str, set[tuple[str, str]]] = {
    ".omo/_delivery/event-ingest/watermark.json": {("bin/ssot/log-rotate.py", "CHECKOUT")},
    ".omo/_delivery/perception-inbox/watermark.json": {("bin/ssot/log-rotate.py", "CHECKOUT")},
    ".omo/_delivery/personal-signals/watermark.json": {("bin/ssot/log-rotate.py", "CHECKOUT")},
    ".omo/_delivery/resident-orchestrator/daemon.log": {("bin/ssot/log-rotate.py", "CHECKOUT")},
    ".omo/_delivery/resident-orchestrator/daemon.pid": {("bin/ssot/log-rotate.py", "CHECKOUT")},
    ".omo/_delivery/resident-orchestrator/receipts.jsonl": {("bin/ssot/log-rotate.py", "CHECKOUT")},
    ".omo/_delivery/resident-orchestrator/watermarks/*": {
        ("bin/gac/check-resident-status.py", "CHECKOUT"),
        ("bin/ssot/log-rotate.py", "CHECKOUT"),
    },
    ".omo/_knowledge/retros/resident": {
        ("bin/gac/fix-frontmatter.py", "CALLER"),
        ("bin/gac/p78-diagnostic-prescan.py", "CHECKOUT"),
        ("bin/gac/retro-reference-engine.py", "CHECKOUT"),
        ("bin/panorama/panorama-collect.py", "CHECKOUT"),
        ("bin/plan/bet-closeout-auto.py", "CHECKOUT"),
        ("bin/plan/bet-ledger.py", "CHECKOUT"),
        ("bin/plan/chain-bind-audit.py", "CHECKOUT"),
        ("bin/reports/quarterly-report.py", "CHECKOUT"),
    },
    ".omo/_knowledge/workflow-mesh/events.jsonl": {("bin/ssot/scene-card-lifecycle.py", "CALLER")},
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
    ("bin/meta/compass_radar.py", "ws_root"): {
        "exprs": ['Path(__file__).resolve().parent.parent / ".omo"'],
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
}
CHECKOUT_MARKERS = ("__file__", "parents[", "code_root")

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


def test_derived_class_readers_are_archived_only():
    """DERIVED = 扫不出模块级根定义。它只允许出现在归档面，否则「未知根」会混进活面。"""
    for table in (SPLIT_EXACT, SPLIT_ANCESTOR):
        for pairs in table.values():
            for rel, klass in pairs:
                if klass == "DERIVED":
                    assert rel.startswith("bin/_archive/"), rel


def test_ledger_family_has_a_single_root_contract_in_bin():
    """台账族的两个 bin 读者必须同一口径，否则「谁读到哪份 ledger」取决于调用者。"""
    _fams, _rows, exact, _an = ledger_measured()
    readers = {rel for rel, _k in exact.get("runtime/omo/event-ledger.sqlite3", set())}
    assert readers == {
        "bin/panorama/panorama-collect.py",
        "bin/panorama/projection-full-refresh.py",
    }


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
