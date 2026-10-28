"""`.omo/state/<dir>/` 写面目录必须被忽略 (BET-Y2Q4-T10-276, ADR-0456 B5 摘库残面).

治理内核包 `projects/omo/src/omo/**` 往 `.omo/state/<dir>/` 写运行态。这些目录既不被跟踪
也不被忽略时，交付期 hook 与 `git add -A` 会把心跳整块扫进 commit，而 merge/release 的脏树
守卫与发布器的 tree_dirty 判据会把它们读成在制工作。

本文件的契约集合由**源码字面量**导出，不是手抄目录名清单 —— 后者会让「绿」只意味着清单没被
扩充，而不是规则存在。派生集合与 `.gitignore` 规则面各由一把独立的尺核对（AST 扫源码 /
git check-ignore 读规则），两者必须一致。
"""

from __future__ import annotations

import ast
import fnmatch
import importlib.util
import re
import subprocess
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT_MODULE = ROOT / "bin" / "lib" / "repo_root.py"

KERNEL_SRC = PurePosixPath("projects/omo/src/omo")
GITIGNORE = PurePosixPath(".gitignore")
STATE_PREFIX = ".omo/state"

# 唯一由**未提交的本机代码**写出的 state 目录：omo.resident.healer 不在 gitlink 钉住的那个
# omo commit 里，所以源码派生看不见它；它在真机上贡献 11 行 untracked 噪声，故规则照立。
MEASURED_ONLY_DIRS = frozenset({"healer"})

# 派生集合的钉死基线 —— 新增写者目录必须在这里显式长出来，同时补一条 .gitignore 规则。
# 每条都可指认到写者：agent-beliefs(drift_monitor/omo_belief/memory_bridge) / agent-cell(
# resident/cell_*) / agent-cell-memory + agent-cell-replay(resident/memory_pipeline:13,
# replay:13) / compute(inference_gateway/swarm_mesh) / daemon(resident/service_*) /
# decision-graph(resident/decision_bridge:57 声明、:63 写) / im-triage + policy-radar
# (pipeline_supervisor) / memory(resident/{chat_engine,epiphany,memory_distiller,pitfall_rag}) /
# notification(resident/notification:107) / refinement-snapshots + refinements
# (resident/refine_rollback:52) / runtime(omo_paths/omo_governance_surfaces_snapshots/
# resident/executor)。
EXPECTED_KERNEL_DIRS = frozenset(
    {
        "agent-beliefs",
        "agent-cell",
        "agent-cell-memory",
        "agent-cell-replay",
        "compute",
        "daemon",
        "decision-graph",
        "im-triage",
        "memory",
        "notification",
        "policy-radar",
        "refinement-snapshots",
        "refinements",
        "runtime",
    }
)

# 2026-10-28T03:45Z 在 canonical 检出 `git status --porcelain --untracked-files=all
# .omo/state` 读出的 15 行；每条都必须被规则命中，否则 B5 的「一次 dev 运行后 status 为空」不成立。
MEASURED_RUNTIME_FILES = (
    "daemon/resident.pid",
    "daemon/service_state.json",
    "healer/approvals.jsonl",
    *(f"healer/heal-{s}.json" for s in
      ("179200", "584418", "6b590d", "86b8e3", "a4407a", "bb3cc9", "d7445b", "dd4d7f", "e350de", "f18369")),
    "memory/distilled_crystallization.json",
    "notification/history.jsonl",
)

# `.gitignore` 里为运行态保留的反选项：规则扩张不得把它们吞掉。
TRACKED_EXCEPTIONS = (
    "collab-dualtrack.yaml",
    "provider-plane.yaml",
    "bos-stdio-migrate-candidates.yaml",
    "m2-ssot-batch-1.yaml",
)


def _checkout_root() -> Path:
    """被检对象的根走 repo_root.code_root()，不由 __file__ 反推。"""
    spec = importlib.util.spec_from_file_location("state_plane_repo_root", REPO_ROOT_MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = Path(module.code_root())
    assert (root / GITIGNORE).is_file(), f"resolver 根不含被测检出: {root}"
    return root


@pytest.fixture()
def checkout_root(monkeypatch) -> Path:
    monkeypatch.setenv("OMOSTATION_ROOT", str(ROOT))
    return _checkout_root()


# ---------------------------------------------------------------- 源码派生尺

# 目录段形状：`.omo/state/` 之后必须是首尾字母数字、中间可含 `-`/`_` 的标识符。落选的两类都是
# **排除项而不是漏项** —— 文件名与 glob 片段（`health.yaml.bak-*`、`system.yaml`、`**`），以及
# f-string 断头（`f"convergence-pulse-{week}.json"` 展平出的 `convergence-pulse-`）。后者带变量后缀，
# 本来就写不出一条静态目录规则，把它算进集合只会让「派生集 = 规则集」这条断言按构造不可满足。
_DIRNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?")


def _chain_segments(node: ast.AST) -> list[str | None]:
    """按源码顺序展平一条 `/` 链的字符串段，非字符串部分计为 None 占位。

    段内再按 `/` 切开，于是 `ROOT / ".omo/state/daemon/x.json"` 与
    `ROOT / ".omo" / "state" / "daemon" / "x.json"` 导出同一个序列；f-string 里的字面
    部分照样进序列，`{var}` 记为 None。
    """
    raw: list[str | None] = []

    def walk(current: ast.AST) -> None:
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
            walk(current.left)
            walk(current.right)
        elif isinstance(current, ast.Constant) and isinstance(current.value, str):
            raw.append(current.value)
        elif isinstance(current, ast.JoinedStr):
            for value in current.values:
                raw.append(value.value) if isinstance(value, ast.Constant) else raw.append(None)
        elif isinstance(current, ast.Call) and getattr(current.func, "id", "") == "Path":
            for arg in current.args:
                walk(arg)

    walk(node)
    segs: list[str | None] = []
    for item in raw:
        if item is None:
            segs.append(None)
        else:
            segs.extend(part for part in item.split("/"))
    return segs


def _state_dirs_in(segs: list[str | None]) -> list[str]:
    """从链式段序列里取出 `.omo/state/<dir>` 的目录段。

    目录段判据是「标识符形状」：`health.yaml.bak-*`、`system.yaml.` 这类文件段和
    `.omo/state/**` 这种 glob 都落在集合外 —— 它们是排除项而不是漏项，所以 glob 兜底
    不能让检测器少认一种形状还自称相等。
    """
    out: list[str] = []
    for i, value in enumerate(segs):
        if value == ".omo" and segs[i + 1 : i + 2] == ["state"] and i + 2 < len(segs):
            candidate = segs[i + 2]
            if candidate and _DIRNAME.fullmatch(candidate):
                out.append(candidate)
    return out


_INLINE_DIR = re.compile(
    r"\.omo/state/(" + _DIRNAME.pattern + r")(?![A-Za-z0-9_.\-])"
)


def derive_state_write_dirs(src_root: Path) -> dict[str, set[str]]:
    """从源码字面量导出 `.omo/state/<dir>/` 的目录段。

    五种写法都要认：`/` 链、整串（`ROOT / ".omo/state/x/y.json"`）、`Path("…")` 直接构造、
    文档串与任意内联串（`_INLINE_DIR`）、f-string 的字面部分。
    """
    found: dict[str, set[str]] = {}

    def note(directory: str, where: str) -> None:
        found.setdefault(directory, set()).add(where)

    for path in sorted(src_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(src_root.parent.parent.parent))
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                for directory in _state_dirs_in(_chain_segments(node)):
                    note(directory, rel)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for directory in _INLINE_DIR.findall(node.value):
                    note(directory, rel)
    return found


# ---------------------------------------------------------------- 规则文本尺

def parse_state_rules(gitignore_text: str) -> list[tuple[bool, tuple[str, ...], bool]]:
    """取出针对 `.omo/state/...` 的规则，返回 (是否反选, 段序列, 是否目录规则)。"""
    rules: list[tuple[bool, tuple[str, ...], bool]] = []
    for line in gitignore_text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        negated = raw.startswith("!")
        pattern = raw[1:] if negated else raw
        if pattern.startswith(STATE_PREFIX):
            is_dir_rule = pattern.endswith("/")
            parts = tuple(part for part in pattern.rstrip("/").split("/") if part)
            rules.append((negated, parts, is_dir_rule))
    return rules


def matches(parts: tuple[str, ...], is_dir_rule: bool, rel_parts: tuple[str, ...]) -> bool:
    """只覆盖本仓用到的形状：目录规则及其任意深度子项、同层 glob（`*` 不跨 `/`）。"""
    if is_dir_rule:
        return len(rel_parts) > len(parts) and all(
            fnmatch.fnmatchcase(real, pat) for real, pat in zip(rel_parts, parts)
        )
    return len(rel_parts) == len(parts) and all(
        fnmatch.fnmatchcase(real, pat) for real, pat in zip(rel_parts, parts)
    )


def rule_ignores(rules: list[tuple[bool, tuple[str, ...], bool]], rel: str) -> bool | None:
    """git 的 last-match-wins；None 表示没有任何规则命中。反选行 `!` 的结论是不忽略。"""
    rel_parts = tuple(part for part in rel.split("/") if part)
    verdict: bool | None = None
    for negated, parts, is_dir_rule in rules:
        if matches(parts, is_dir_rule, rel_parts):
            verdict = not negated
    return verdict


def ignored_by_git(root: Path, probes: list[str]) -> set[str]:
    """让 git 自己裁决 —— 与规则文本尺互为反证。"""
    proc = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", *probes],
        capture_output=True,
        text=True,
    )
    assert proc.returncode in (0, 1), proc.stderr
    return {line for line in proc.stdout.splitlines() if line}


def _state_text(root: Path) -> str:
    return (root / GITIGNORE).read_text(encoding="utf-8")


# ------------------------------------------------------------------------ 用例

def test_derivation_is_not_a_no_op(tmp_path: Path) -> None:
    """检测器自证：五种字面量形状都要命中，文件名段与 f-string 断头都要排除。"""
    module = tmp_path / "projects" / "omo" / "src" / "omo" / "synthetic.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            (
                "from pathlib import Path",
                "ROOT = Path('.')",
                "week = '2026-W44'",
                'CHAIN = ROOT / ".omo" / "state" / "synthetic-plane" / "card.json"',
                'STRING = ROOT / ".omo/state/synthetic-string/shadow.json"',
                'FILE_GLOB = ROOT / ".omo/state/synthetic-plane.yaml.bak-20261028"',
                'NESTED = ROOT / "%s" / "synthetic-nested" / "a" / "b.json"' % STATE_PREFIX,
                'DIRECT = Path(".omo/state/synthetic-direct/thing.json")',
                'DOC = """持久化为 .omo/state/synthetic-doc/graph.jsonl，每行一条 JSON"""',
                'FRAGMENT = ROOT / ".omo/state" / f"synthetic-{week}-pulse" / "x.json"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    dirs = derive_state_write_dirs(module.parent)
    assert {
        "synthetic-plane",
        "synthetic-string",
        "synthetic-nested",
        "synthetic-direct",
        "synthetic-doc",
    } <= set(dirs), sorted(dirs)
    # 两类排除项：文件名段不是目录；f-string 断头（尾 `-` 段）带变量后缀，写不出一条静态目录规则。
    assert "synthetic-plane.yaml.bak-20261028" not in dirs
    assert not [d for d in dirs if d.endswith(("-", "_"))], sorted(dirs)


def test_kernel_state_write_dirs_are_the_reviewed_list(checkout_root: Path) -> None:
    """派生集合与基线**集合相等**：漏一种形状或新增长出目录都会在这里红。"""
    dirs = derive_state_write_dirs(checkout_root / KERNEL_SRC)
    assert set(dirs) == EXPECTED_KERNEL_DIRS, (
        f"多出 {sorted(set(dirs) - EXPECTED_KERNEL_DIRS)} / 缺少 {sorted(EXPECTED_KERNEL_DIRS - set(dirs))}"
    )


def test_every_kernel_state_write_dir_is_ignored(checkout_root: Path) -> None:
    """内核包写出的每个 `.omo/state/<dir>/` 都必须被规则命中 —— 两把尺读数一致。"""
    dirs = sorted(set(derive_state_write_dirs(checkout_root / KERNEL_SRC)) | MEASURED_ONLY_DIRS)
    assert dirs
    probes = [f"{STATE_PREFIX}/{d}/__probe__.json" for d in dirs]
    git_says = ignored_by_git(checkout_root, probes)
    rules = parse_state_rules(_state_text(checkout_root))
    text_says = {p for p in probes if rule_ignores(rules, p) is True}
    missing = sorted(set(probes) - git_says)
    assert not missing, f"以下 state 目录的内容不会被 git 忽略: {missing}"
    assert git_says == text_says, f"规则文本尺与 git 不一致: {git_says ^ text_says}"


def test_missing_rule_is_named_by_the_detector(checkout_root: Path) -> None:
    """摘掉一条规则，文本尺必须点名它 —— 防「按构造就绿」。"""
    text = _state_text(checkout_root)
    rules = parse_state_rules(text)
    assert rule_ignores(rules, f"{STATE_PREFIX}/daemon/resident.pid") is True
    gutted = "\n".join(
        line for line in text.splitlines() if line.strip() != f"{STATE_PREFIX}/daemon/"
    )
    reduced = parse_state_rules(gutted)
    assert rule_ignores(reduced, f"{STATE_PREFIX}/daemon/resident.pid") is None
    for directory in MEASURED_ONLY_DIRS:
        assert rule_ignores(reduced, f"{STATE_PREFIX}/{directory}/approvals.jsonl") is True


def test_measured_runtime_files_are_no_longer_loose(checkout_root: Path) -> None:
    """真机上那 15 行逐条命中，B5 的 status 判据才成立。"""
    probes = [f"{STATE_PREFIX}/{name}" for name in MEASURED_RUNTIME_FILES]
    assert len(probes) == 15
    assert ignored_by_git(checkout_root, probes) == set(probes)


def test_tracked_state_exceptions_are_not_swallowed(checkout_root: Path) -> None:
    """唯一被跟踪的 state 文件与四条反选，都必须继续不被忽略。"""
    tracked = subprocess.run(
        ["git", "-C", str(checkout_root), "ls-files", STATE_PREFIX],
        capture_output=True,
        text=True,
    ).stdout.split()
    assert tracked == [f"{STATE_PREFIX}/collab-dualtrack.yaml"], tracked
    for name in TRACKED_EXCEPTIONS:
        rel = f"{STATE_PREFIX}/{name}"
        assert rule_ignores(parse_state_rules(_state_text(checkout_root)), rel) is False, rel
        assert rel not in ignored_by_git(checkout_root, [rel]), rel
