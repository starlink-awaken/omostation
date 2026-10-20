"""ADR-0456 :246 / BET-Y2Q4-T10-261 — 跨安装位 import 错包的启动断言契约。

判据本体在 `bin/lib/repo_root.py` 的 `assert_import_root()` / `import_root_report()`。
本文件钉 spec §2 的 C1—C4 与 §3 的 G1—G3，其中 G1-④ 是**变异对照**：向源码注入
一处让判定恒真 / 让输入守卫失效的改动，断言对应用例当场失守 —— 否则「绿」可能只是
装置没命中 (AGENTS.md §7「扫源码的门禁必须自证」)。
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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bin" / "lib"))

import repo_root  # noqa: E402

REPO_ROOT_PY = REPO / "bin" / "lib" / "repo_root.py"
SENTINELS = {
    "OMOSTATION_STATE_ROOT": "/sentinel/state-root",
    "OMO_EVENT_LEDGER_DB": "/sentinel/ledger.sqlite3",
}
NEW_NAMES = ("assert_import_root", "import_root_report")


def _load(source_text: str, name: str):
    """把 (可能被变异过的) 源码装成独立模块, 不碰 sys.modules 里的正主。"""
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source_text, f"<{name}>", "exec"), module.__dict__)
    return module


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> dict[str, Path]:
    """一棵假的「双检出」: x/ 与 other/ 互不包含, 对应 spec G1 ①② 的形状。"""
    root = tmp_path_factory.mktemp("import-root")
    (root / "x" / "pkg").mkdir(parents=True)
    (root / "other" / "pkg").mkdir(parents=True)
    good = root / "x" / "pkg" / "m.py"
    bad = root / "other" / "pkg" / "m.py"
    for p in (good, bad):
        p.write_text("VALUE = 1\n", encoding="utf-8")
    return {"root": root, "x": root / "x", "good": good, "bad": bad}


# ── G1 ────────────────────────────────────────────────────────────────────────


def test_g1_positive_returns_the_confirmed_root(tree) -> None:
    """① 在根下 ⇒ 返回解析后的 root, 不抛。"""
    returned = repo_root.assert_import_root(tree["good"], root=tree["x"])
    assert returned == tree["x"].resolve()
    report = repo_root.import_root_report(tree["good"], root=tree["x"])
    assert report["under"] is True and report["ok"] is True


def test_g1_negative_raises_and_names_both_roots(tree) -> None:
    """② 不在根下 ⇒ 抛, 且消息同时打出两侧绝对路径 (不猜哪条 .pth)。"""
    with pytest.raises(repo_root.ImportRootMismatch) as exc:
        repo_root.assert_import_root(tree["bad"], root=tree["x"])
    message = str(exc.value)
    assert str(tree["x"].resolve()) in message, message
    assert str(tree["bad"]) in message or str(tree["bad"].resolve()) in message, message
    assert ".pth" in message, message
    report = repo_root.import_root_report(tree["bad"], root=tree["x"])
    assert report["under"] is False and report["ok"] is False


@pytest.mark.parametrize("bad_input", ["", "   ", "pkg/m.py", "./pkg/m.py"])
def test_g1_unreadable_inputs_never_pass_silently(tree, bad_input) -> None:
    """③ 空 / 相对 ⇒ 同样抛，且**由输入守卫抛**。

    `Path("")` 会 resolve 成 cwd、`Path("pkg/m.py")` resolve 后按几何也不在根下 ——
    两种情况下调用方都会看到「抛了」，但那是「判成了不一致」不是「判不了」。spec C1
    要的是「读不出来」与「读出来没问题」可分，所以消息必须点名「无从判定」。
    """
    with pytest.raises(repo_root.ImportRootMismatch) as exc:
        repo_root.assert_import_root(bad_input, root=tree["x"])
    assert "无从判定" in str(exc.value), str(exc.value)
    assert repo_root.import_root_report(bad_input, root=tree["x"])["under"] is None


@pytest.mark.parametrize("bad_input", [None, "", "   ", "pkg/m.py", "./pkg/m.py"])
def test_g1_none_module_file_is_the_self_probe_not_an_unreadable_input(bad_input) -> None:
    """C1 与 C2 对 `None` 的语义**刻意不同**，这条把它钉住以免被"统一成抛"抹平。

    C1 `assert_import_root(None)` 抛（断言面不许有隐式被检对象）；
    C2 `import_root_report(None)` 探 repo_root 自己所在的检出（spec 逐字：
    「`module_file=None` 时探的是 `repo_root` 自己所在检出的码根」），返回**布尔**而不是 None。
    """
    with pytest.raises(repo_root.ImportRootMismatch):
        repo_root.assert_import_root(bad_input)
    report = repo_root.import_root_report(bad_input)
    if bad_input is None:
        assert report["under"] is True and report["ok"] is True, report
        assert report["module_file"] == str(Path(repo_root.__file__).resolve()), report
    else:
        assert report["under"] is None and report["ok"] is False, report


def test_g1_root_equal_to_module_file_counts_as_under(tree) -> None:
    """边界: 「含等于 root 本身」(spec C1) —— 目录对象本身也算落在根下。"""
    assert repo_root.import_root_report(tree["x"], root=tree["x"])["under"] is True


def test_g1_mutation_control_under_judgement_cannot_be_constant_true(tree) -> None:
    """④-a 把 `under` 判定改成恒真 ⇒ 反向用例 ② 必须当场失守 (否则 ② 是空判据)。"""
    source = REPO_ROOT_PY.read_text(encoding="utf-8")
    mutated = source.replace(
        "    try:\n        target.relative_to(base)\n    except ValueError:\n        under = False\n    else:\n        under = True\n",
        "    under = True\n",
    )
    assert mutated != source, "变异装置没命中被测判定本体"
    module = _load(mutated, "_rr_mutated_under_true")
    with pytest.raises(repo_root.ImportRootMismatch):
        # 正主仍须抛 —— 变异面与正主不同源, 否则这条断言按构造就绿
        repo_root.assert_import_root(tree["bad"], root=tree["x"])
    try:
        module.assert_import_root(tree["bad"], root=tree["x"])
    except module.ImportRootMismatch:
        pytest.fail("恒真判定下反向用例仍红, 说明 ② 依赖的不是这个判定")
    assert module.import_root_report(tree["bad"], root=tree["x"])["ok"] is True


def test_g1_mutation_control_input_guards_cannot_fold_into_silent_pass(tree) -> None:
    """④-b 把「判不了」折叠成「通过」⇒ 边界用例 ③ 必须当场失守。

    这是 spec C1 那句「不得静默通过」的唯一可执行反证：变异体对空 / None / 相对一律
    `return base`，正主一律抛。只断言"抛了"不算自证（几何判定也会造成抛）。
    """
    source = REPO_ROOT_PY.read_text(encoding="utf-8")
    guards = (
        '    if module_file is None or not str(module_file).strip():\n'
        '        raise ImportRootMismatch(f"无从判定: module_file 为空 (期望检出根 {base})")\n'
        '    target_raw = Path(str(module_file))\n'
        '    if not target_raw.is_absolute():\n'
        '        raise ImportRootMismatch(f"无从判定: module_file 是相对路径 {target_raw} (期望检出根 {base})")\n'
    )
    assert source.count(guards) == 1, "变异装置没命中输入守卫"
    fold = (
        '    if module_file is None or not str(module_file).strip():\n'
        '        return base\n'
        '    target_raw = Path(str(module_file))\n'
        '    if not target_raw.is_absolute():\n'
        '        return base\n'
    )
    mutant = _load(source.replace(guards, fold), "_rr_mutated_fold")
    for value in ("", "   ", None, "pkg/m.py", "./pkg/m.py"):
        with pytest.raises(repo_root.ImportRootMismatch):
            repo_root.assert_import_root(value, root=tree["x"])
        mutant.assert_import_root(value, root=tree["x"])  # 变异体不抛 ⇒ ③ 真依赖这两条守卫


def test_g1_mutation_control_undecidable_is_not_collapsed_into_false(tree) -> None:
    """④-c 把 `under=None` 写成 `under=False` ⇒ C2 的「判不了」面必须当场失守。

    对断言面而言 False 与 None 都是「不 ok」，所以只有钉 `is None` 的用例能发现这种
    折叠；它是 AGENTS.md §7⑨「坏了与空同形」的同一形状。
    """
    source = REPO_ROOT_PY.read_text(encoding="utf-8")
    old = '        return {"expected_root": str(base_raw), "module_file": str(target_raw), "under": None, "ok": False}'
    assert source.count(old) == 1, "变异装置没命中「相对/非绝对」那条返回"
    mutant = _load(source.replace(old, old.replace('"under": None', '"under": False')), "_rr_mutated_none_shape")
    for value in ("pkg/m.py", "rel/m.py"):
        assert repo_root.import_root_report(value, root=tree["x"])["under"] is None
        assert mutant.import_root_report(value, root=tree["x"])["under"] is False



# ── G2 ────────────────────────────────────────────────────────────────────────


def test_g2_cross_root_pair_and_same_root_pair_come_from_one_scan(tree) -> None:
    """M2/M4 两面同批产出: 只断言一侧 (「报得出错」或「报得出对」) 都不算绿。"""
    # M2 形状: 期望码根 = 这个检出, 实际导入根 = 另一棵树 (canonical 副本赢过 worktree)
    mismatch = repo_root.import_root_report(tree["bad"], root=repo_root.code_root())
    assert mismatch["under"] is False and mismatch["ok"] is False, mismatch
    assert mismatch["expected_root"] == str(repo_root.code_root()), mismatch
    # M4 形状: 同根 (常驻进程按构造落在自己那棵树时不得误报)
    match = repo_root.import_root_report(repo_root.code_root() / "bin" / "lib" / "repo_root.py")
    assert match["under"] is True and match["ok"] is True, match
    # 两面共用同一判定 ⇒ 键集与「判不了」形状一致
    assert set(mismatch) == set(match) == {"expected_root", "module_file", "under", "ok"}


def test_g2_self_probe_is_the_identity_and_never_undecidable() -> None:
    """`module_file=None` 探 repo_root 自己 —— 它必须给布尔而不是 None, 否则 C3 的观测面无意义。"""
    report = repo_root.import_root_report()
    assert report["under"] is True, report
    assert report["module_file"] == str(Path(repo_root.__file__).resolve()), report


# ── C3 / C4 ───────────────────────────────────────────────────────────────────


def test_c3_roots_report_import_root_is_absent_probe_not_ok(tree) -> None:
    saved = os.environ.pop(repo_root.IMPORT_PROBE_ENV, None)
    try:
        field = repo_root.roots_report()["import_root"]
    finally:
        if saved is not None:
            os.environ[repo_root.IMPORT_PROBE_ENV] = saved
    assert field["probed"] is False, field
    assert field["ok"] is not True, field
    assert field["under"] is None, field


def test_c3_probe_env_turns_ok_into_a_boolean_for_both_shapes(tmp_path, tree) -> None:
    inside = tree["good"]
    outside_dir = tmp_path / "elsewhere" / "pkg"
    outside_dir.mkdir(parents=True)
    outside = outside_dir / "m.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")

    env = {**os.environ, repo_root.IMPORT_PROBE_ENV: str(inside)}
    out = subprocess.run(
        [sys.executable, str(REPO_ROOT_PY), "--json"],
        capture_output=True, text=True, env=env, cwd=REPO, check=True,
    )
    field = json.loads(out.stdout)["import_root"]
    assert field["probed"] is True and isinstance(field["ok"], bool), field

    env[repo_root.IMPORT_PROBE_ENV] = str(outside)
    out2 = subprocess.run(
        [sys.executable, str(REPO_ROOT_PY), "--json"],
        capture_output=True, text=True, env=env, cwd=REPO, check=True,
    )
    field2 = json.loads(out2.stdout)["import_root"]
    assert field2["probed"] is True and field2["under"] is False and field2["ok"] is False, field2


def test_c3_unprobeable_module_name_is_honest_not_ok(tmp_path) -> None:
    """探针名既不是文件也不是可定位 spec ⇒ under=None、ok=False, 不得报 ok=True。"""
    env = {**os.environ, repo_root.IMPORT_PROBE_ENV: "no_such_module_anywhere_261"}
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT_PY), "--json"],
        capture_output=True, text=True, env=env, cwd=REPO, check=True,
    )
    field = json.loads(proc.stdout)["import_root"]
    assert field == {"probed": True, "expected_root": field["expected_root"], "module_file": None,
                    "under": None, "ok": False}, field


def test_c4_detection_never_moves_the_exit_code(tmp_path, tree) -> None:
    """C4: 探到不一致也只观测。exit code 判据 (main() 恒 0) 不因本契约改变。"""
    for probe in (None, str(tree["bad"]), "no_such_module_anywhere_261"):
        env = {**os.environ}
        env.pop(repo_root.IMPORT_PROBE_ENV, None)
        if probe:
            env[repo_root.IMPORT_PROBE_ENV] = probe
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT_PY), "--json"],
            capture_output=True, text=True, env=env, cwd=REPO,
        )
        assert proc.returncode == 0, (probe, proc.stderr)
        assert repo_root.main(["--json"]) == 0
    source = REPO_ROOT_PY.read_text(encoding="utf-8")
    body = source[source.index("def main("):source.index("__all__ = (")]
    assert "return 0" in body and "raise SystemExit" not in body.split("if __name__")[0], body
    # 判据本体未被改写: main() 在 origin/main 上就是这 17 行, 本契约只加了 roots_report 的一个键
    base = subprocess.run(
        ["git", "-C", str(REPO), "show", "origin/main:bin/lib/repo_root.py"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert base[base.index("def main("):base.index("__all__ = (")] == body


# ── G3 ────────────────────────────────────────────────────────────────────────


def _zero_arg_profile_resolvers(module) -> set[str]:
    """复刻 tests/unit/test_b1_ledger_call_time.py 的探测语义: 零参调用 + 返回 Path + 随 profile 位移。"""
    found: set[str] = set()
    saved = {key: os.environ.get(key) for key in (*SENTINELS, "OMOSTATION_ROOT")}
    try:
        for name in module.__all__:
            fn = getattr(module, name, None)
            if not callable(fn):
                continue
            os.environ["OMOSTATION_ROOT"] = str(REPO)
            os.environ.update(SENTINELS)
            try:
                declared = fn()
            except TypeError:
                continue
            for key, value in saved.items():
                os.environ.pop(key, None)
                if value is not None:
                    os.environ[key] = value
            os.environ["OMOSTATION_ROOT"] = str(REPO)
            try:
                undeclared = fn()
            except TypeError:
                continue
            if isinstance(declared, Path) and declared != undeclared:
                found.add(name)
    finally:
        for key, value in saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value
    return found


def test_g3_new_names_are_not_profile_root_resolvers() -> None:
    """新缝不得被「零参 callable ⇒ 根解析器」那类判据误认 (spec G3)。"""
    resolvers = _zero_arg_profile_resolvers(repo_root)
    assert {"state_root", "event_ledger_path"} <= resolvers, resolvers
    assert not set(NEW_NAMES) & resolvers, resolvers
    assert isinstance(repo_root.import_root_report(), dict)
    with pytest.raises(TypeError):
        repo_root.assert_import_root()  # 必填参数 ⇒ 按构造不进零参探测


def test_g3_new_names_are_not_checkout_root_locators() -> None:
    """同样不得被 tests/unit/test_resident_write_plane_split.py 的定位器谓词收进通过集。

    谓词五条: no-file-anchor / no-state-marker / refs-marker / raises / zero-required-args。
    这里只算与本契约相关的两条, 结论是两名都**被拒** —— 通过集仍是 {canonical_root}。
    """
    tree = ast.parse(REPO_ROOT_PY.read_text(encoding="utf-8"))
    all_names: set[str] = set()
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AnnAssign) else [])
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "__all__":
                all_names = set(ast.literal_eval(node.value))
    assert all_names, "repo_root.py 没有 __all__ 字面量"
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    accepted: set[str] = set()
    for name in sorted(all_names & set(defs)):
        fn = defs[name]
        args = fn.args
        required = len(args.posonlyargs) + len(args.args) - len(args.defaults)
        zero_required = required == 0 and all(d is not None for d in args.kw_defaults)
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        refs_marker = "MARKER" in names
        raises = any(isinstance(r, ast.Raise) for r in ast.walk(fn))
        if zero_required and refs_marker and raises:
            accepted.add(name)
    assert accepted == {"canonical_root"}, sorted(accepted)
    assert NEW_NAMES[0] not in accepted and NEW_NAMES[1] not in accepted


def test_g3_import_root_report_is_exception_safe_under_host_state_loss(tmp_path) -> None:
    """诊断面不得抛: 它是给门禁和 CLI 用的, 一旦抛就把观测变成故障 (含 HOME 丢失面)。"""
    env = {**os.environ}
    for key in ("OMOSTATION_ROOT", "OMOSTATION_STATE_ROOT", "OMO_EVENT_LEDGER_DB", repo_root.IMPORT_PROBE_ENV):
        env.pop(key, None)
    env["HOME"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util,json,sys;"
         f"spec=importlib.util.spec_from_file_location('rr', {str(REPO_ROOT_PY)!r});"
         "rr=importlib.util.module_from_spec(spec);spec.loader.exec_module(rr);"
         "print(json.dumps([rr.import_root_report(''), rr.import_root_report(None),"
         " rr.import_root_report('rel/m.py'), rr.roots_report()['import_root']], default=str))"],
        capture_output=True, text=True, env=env, cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    readings = json.loads(proc.stdout)
    assert all(item["under"] is None or isinstance(item.get("under"), bool) for item in readings), readings
    assert readings[0]["ok"] is False and readings[2]["ok"] is False, readings
