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

⚠️ 本轮实测的决定性结论: bin/ 侧**没有任何读者**解析到 state 根 (类别只有 CHECKOUT /
CALLER / DERIVED)。因此「读写同根」在不动 `bin/` 的前提下**结构上不可能达成**，本文件把
这份 split 清单钉成**已登记的现状**而不是「已经收敛」。台账 circuit_breaker 明确
「需要改 bin/ 读者 → 停下登记而不是扩大 PR」，所以这里是登记，不是豁免的省略。

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

# 12 个族 / 33 对。类别 = 该 bin 文件里锚点的根: CHECKOUT=检出常量, CALLER=函数参数
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
    ".omo/_delivery/resident-orchestrator/daemon.log": {
        ("bin/ssot/resident-orchestrator-daemon.py", "CHECKOUT"),
    },
    ".omo/_delivery/resident-orchestrator/daemon.pid": {
        ("bin/ssot/resident-orchestrator-daemon.py", "CHECKOUT"),
    },
    ".omo/_delivery/resident-orchestrator/watermarks/*": {
        ("bin/ssot/resident-orchestrator-daemon.py", "CHECKOUT"),
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
        ("bin/panorama/projection-full-refresh.py", "CHECKOUT"),
    },
}

# 9 个族 / 17 对。log-rotate 是**目录级**清理者，它按祖先路径删日志 —— 写者改道而它没跟上
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
}
CHECKOUT_MARKERS = ("__file__", "parents[", "code_root")

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


def test_no_bin_reader_resolves_to_state_root(measured):
    """本轮的决定性读数: bin/ 侧零 STATE 读者 ⇒ 「读写同根」不可能靠改 omo 达成。

    这条不是「已经收敛」的证据，是**登记**：它说明 I3 的后半必须落在 bin/ 侧一轮，
    而台账 circuit_breaker 禁止本轮扩面。若将来有 bin 读者改到 state 根，本用例**转绿的方向
    是红** —— 那时要同步缩小 SPLIT_* 两张表。
    """
    _fams, rows, _ex, _an = measured
    assert _state_readers(rows) == []


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
        if via := spec.get("checkout_via"):
            assert _module_classes(ROOT / rel, {})[via] == "CHECKOUT", (rel, via)
        elif spec.get("checkout"):
            assert any(marker in " ".join(exprs) for marker in CHECKOUT_MARKERS), (rel, exprs)


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
