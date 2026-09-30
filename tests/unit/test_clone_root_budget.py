"""整仓克隆必须有独立预算, 不得复用「单次网络操作」的预算 (2026-09-30).

## 缺陷

`cmd_create` 里的根克隆原先是::

    proc = git(None, *clone_args, timeout=GIT_TIMEOUT_NETWORK_SECONDS)   # 60s

而 `GIT_TIMEOUT_NETWORK_SECONDS` 的语义是**一次网络操作**(`ls-remote` 探针、
单 revision `fetch`) —— 文件里另外两处 60s 放在那两类操作上是合理的, 只有整仓
`git clone --no-local` 是异常值。

实测该命令 **26.73s / 118MB .git / 10054 个文件检出**(负载 ~120)。其中大头是
**checkout 10054 个文件**而非对象传输, 所以它对机器负载高度敏感: 负载 250-400
时同样命令超过 60s, onboard 在真正开工前就失败(2026-09-30 连续三次)。

这是本轮「外层预算小于实际工作量」系列的第三处 —— 前两处是
`governance-semantic-gate`(60s < 内层单子检查 180s)与门禁 clone 步。

## 为什么用 AST 而不是 grep

断言要区分「**这个调用点**用的哪个常量」和「文件里提到过哪个常量」。文本 grep
分不开这两者 —— 注释里写上新常量名就能骗过 grep。AST 直接定位 `git(...)` 调用
并读取其 `timeout` 关键字实参, 无法被注释或字符串误导。
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "agent_clone_budget", WORKSPACE / "bin" / "gac" / "agent-clone.py"
)
assert _spec and _spec.loader
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)

SOURCE = (WORKSPACE / "bin" / "gac" / "agent-clone.py").read_text(encoding="utf-8")


def _list_literal_names(tree: ast.AST) -> dict[str, str]:
    """收集 `name = ["<first string>", ...]` 形式的列表首元素。

    根克隆的调用是 `git(None, *clone_args, ...)`, 子命令经由 `clone_args = ["clone"]`
    间接传入, 因此必须解析这个局部列表才能定位到「哪个调用点是 clone」。
    """
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and isinstance(node.value, ast.List)):
            continue
        first = node.value.elts[0] if node.value.elts else None
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names[target.id] = first.value
    return names


def _timeout_by_subcommand() -> dict[str, list[str]]:
    """AST 遍历: 记录每个 git() 调用点按子命令归类的 timeout 常量名。

    同时处理直接字面量子命令与 `*<局部列表>` 解包两种形式。
    返回 {subcommand: [常量名, ...]}; 一个子命令可能有多处调用点。
    """
    tree = ast.parse(SOURCE)
    list_names = _list_literal_names(tree)
    found: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "git":
            continue
        sub = None
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                inner = arg.value
                if isinstance(inner, ast.Name) and inner.id in list_names:
                    sub = list_names[inner.id]
                break
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                sub = arg.value
                break
        if sub is None:
            continue
        name = None
        for kw in node.keywords:
            if kw.arg == "timeout":
                if isinstance(kw.value, ast.Name):
                    name = kw.value.id
                elif isinstance(kw.value, ast.Constant):
                    name = repr(kw.value.value)
                break
        found.setdefault(sub, []).append(name)
    return found


def test_root_clone_uses_its_own_budget() -> None:
    found = _timeout_by_subcommand()
    assert "clone" in found, f"未在 AST 中找到 git clone 调用点; 实际子命令: {sorted(found)}"
    for used in found["clone"]:
        assert used == "GIT_CLONE_ROOT_TIMEOUT_SECONDS", (
            f"整仓 clone 仍在用 {used!r} —— 该常量语义是「一次网络操作」, "
            "对整仓 clone 结构性不足"
        )


def test_single_network_operations_keep_the_network_budget() -> None:
    """ls-remote 探针与单 revision fetch 仍是网络操作, 60s 合理, 不应被一起放大。

    反向护栏: 防止后来的修复把预算无差别地调大, 拖慢真正的卡死检测。
    """
    found = _timeout_by_subcommand()
    for subcommand in ("ls-remote", "fetch"):
        assert subcommand in found, f"未找到 git {subcommand} 调用点; 实际: {sorted(found)}"
        for used in found[subcommand]:
            assert used != "GIT_CLONE_ROOT_TIMEOUT_SECONDS", (
                f"git {subcommand} 被误用整仓克隆预算 {used!r} —— "
                "单次网络操作不该拿到 checkout 全仓的预算"
            )


def test_root_clone_budget_exceeds_network_budget() -> None:
    """整仓克隆预算必须严格大于单次网络操作预算, 否则这个拆分没有意义。"""
    assert ac.GIT_CLONE_ROOT_TIMEOUT_SECONDS > ac.GIT_TIMEOUT_NETWORK_SECONDS, (
        f"整仓预算 {ac.GIT_CLONE_ROOT_TIMEOUT_SECONDS}s 未大于网络预算 "
        f"{ac.GIT_TIMEOUT_NETWORK_SECONDS}s"
    )


def test_root_clone_budget_covers_measured_cost() -> None:
    """预算必须覆盖实测值并留足负载余量。

    实测 26.73s(负载 ~120, 10054 文件检出), 负载 250+ 时超过原 60s。
    30s 门槛只挡住「比实测还小」; 180s 门槛对应约 6.7 倍余量, 覆盖负载 400 区间。
    """
    assert ac.GIT_CLONE_ROOT_TIMEOUT_SECONDS >= 30.0, (
        f"{ac.GIT_CLONE_ROOT_TIMEOUT_SECONDS}s 低于实测 26.73s 的安全下限"
    )
    assert ac.GIT_CLONE_ROOT_TIMEOUT_SECONDS >= 180.0, (
        f"{ac.GIT_CLONE_ROOT_TIMEOUT_SECONDS}s 对负载敏感的全仓检出余量不足"
    )


def test_root_clone_budget_is_env_configurable(monkeypatch) -> None:
    """与本文件其他预算一致, 可用环境变量覆盖而不必改代码。"""
    monkeypatch.setenv("AGENT_CLONE_GIT_CLONE_ROOT_TIMEOUT", "123.0")
    reloaded = _reload()
    assert reloaded.GIT_CLONE_ROOT_TIMEOUT_SECONDS == 123.0


def _reload():
    spec = importlib.util.spec_from_file_location(
        "agent_clone_budget_env", WORKSPACE / "bin" / "gac" / "agent-clone.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_cmd_create() -> ast.FunctionDef:
    for node in ast.walk(ast.parse(SOURCE)):
        if isinstance(node, ast.FunctionDef) and node.name == "cmd_create":
            return node
    raise AssertionError("未找到 cmd_create")


def test_submodule_clone_still_bounded_per_path() -> None:
    """逐子模块克隆(PR #4572)必须保持「每个路径独立预算」, 不被本次改动回退成整批。

    这是反向护栏: 整仓预算变大不等于可以把子模块改回一条批量命令 ——
    那正是 PR #4572 修掉的缺陷(一次 834MB / 2755 commits 塞进 60s)。
    """
    body = ast.get_source_segment(SOURCE, _find_cmd_create()) or ""
    assert "for path in initialize_paths:" in body, "未找到逐子模块克隆循环"
    # 循环体内不得再出现「一次性 initialize_paths 列表 + 单条 submodule update」
    assert body.count('"submodule"') >= 2, "逐子模块循环体应含 submodule 调用"
