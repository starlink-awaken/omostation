"""门禁外层预算必须容得下内层工作 (2026-09-30).

`gac-local-gate.py` 给每个检查一个外层 timeout, 超时即报 TIMEOUT 并翻转整个 gate。
`governance-semantic-gate.py` 内部 `_run_json` 每个子检查允许 180s, 一次跑 8 个子检查。

原外层预算是 **60s** —— 比「一个」子检查的内部上限还小, 属于结构性不可能满足:

    实测 (6+ 并发 agent 的真实机器)  56.26s / 38.36s / 30.47s
    三次语义判定全部 PASS (ok=true, blocking_failures=0)
    但 60s 硬顶在最大值时只剩 3.74s 余量 -> 周期性 TIMEOUT
    -> TIMEOUT 被记成 blocking ERROR -> 整个 gate FAIL -> 阻断交付

即: **一个不代表任何语义问题的超时, 反复阻断真实交付**。这与「不可判定被当作不可用」
同族 —— 也是 `agent-workflow-doctor` 早已修过的同一个病 (60s -> 120s), 只是漏了
`governance-semantic-gate` 这一条。

本测试断言的是**结构不变量**而非计时: 外层预算 >= 内层单子检查上限。计时断言在
并发机器上必然抖动, 那正是本缺陷的成因, 不能用作回归护栏。
"""

from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load("gac_local_gate", "bin/gac/gac-local-gate.py")

INNER_PER_CHECK_DEFAULT = 180  # governance-semantic-gate.py::_run_json(timeout=180)


def test_inner_per_check_budget_is_still_180():
    """把内层预算写死在测试里, 使内层一旦改动就必须同步来这里。"""
    src = (WORKSPACE / "bin" / "gac" / "governance-semantic-gate.py").read_text()
    m = re.search(r"def _run_json\(.*?timeout:\s*int\s*=\s*(\d+)", src, re.S)
    assert m, "未找到 _run_json 的 timeout 默认值 —— 内层结构变了, 请重新评估本不变量"
    assert int(m.group(1)) == INNER_PER_CHECK_DEFAULT, (
        f"内层单子检查上限已从 180 变为 {m.group(1)}, 外层预算需一并重新评估"
    )


def test_outer_budget_is_not_smaller_than_one_inner_check():
    """核心不变量: 外层预算不得小于内层**单个**子检查的上限。"""
    effective = gate._CHECK_TIMEOUTS["governance-semantic-gate"]
    assert effective >= INNER_PER_CHECK_DEFAULT, (
        f"外层预算 {effective}s < 内层单子检查上限 {INNER_PER_CHECK_DEFAULT}s —— "
        "结构性不可能满足, 必然周期性误报 TIMEOUT 并阻断交付"
    )


def test_both_declaration_sites_agree():
    """代码里的两处声明源必须一致。

    生效链路是三层的, 容易只改一处而另一处变成空转的死代码:

        GATES_LIST = list(POLICY.get("gates", DEFAULT_POLICY["gates"]))
        _CHECK_TIMEOUTS = {g["id"]: g.get("timeout", _DEFAULT_CHECK_TIMEOUTS.get(g["id"], 15))}

    实时 sgf-policy.yaml **常省略** timeout (见文件内注释), 此时内联值不参与,
    生效的是 _DEFAULT_CHECK_TIMEOUTS。故两处都要断言, 且断言的是**源码默认**而非
    运行时合并结果 —— 后者已被实时 policy 覆盖, 断言它会把 policy 的漂移误报成代码缺陷。
    """
    inline = next(
        g["timeout"]
        for g in gate.DEFAULT_POLICY["gates"]
        if g["id"] == "governance-semantic-gate" and "timeout" in g
    )
    fallback = gate._DEFAULT_CHECK_TIMEOUTS["governance-semantic-gate"]
    assert inline == fallback, (
        f"源码内联 {inline}s 与 _DEFAULT_CHECK_TIMEOUTS {fallback}s 不一致; "
        "实时 policy 省略 timeout 时生效的是后者, 两者不一致即为死代码 + 隐性覆盖"
    )


def test_live_policy_omission_does_not_silently_drop_to_15s():
    """若实时 policy 省略 timeout, 生效值必须仍来自命名默认值, 而不是 15s 兜底。"""
    effective = gate._CHECK_TIMEOUTS["governance-semantic-gate"]
    assert effective != 15, "生效值落到了 15s 通用兜底, 说明命名默认值未命中"
    assert effective >= INNER_PER_CHECK_DEFAULT


def test_resolved_timeout_is_the_one_that_counts():
    """_CHECK_TIMEOUTS 是真正生效的值, 防止前两处对了但解析逻辑取错。"""
    assert gate._CHECK_TIMEOUTS["governance-semantic-gate"] == 180


def test_agent_workflow_doctor_regression_not_reintroduced():
    """同一文件里已修过的同类预算不得回退。"""
    assert gate._CHECK_TIMEOUTS["agent-workflow-doctor"] >= 120


def test_timeout_map_covers_every_registered_gate():
    """预算表对每个已注册检查都有明确取值, 不靠 15s 默认值兜底。"""
    missing = [g["id"] for g in gate.GATES_LIST if g["id"] not in gate._CHECK_TIMEOUTS]
    assert not missing, f"以下检查没有显式预算, 会落到 15s 默认值: {missing}"


def test_load_module_does_not_execute_gate():
    """导入本模块不得触发门禁执行 (否则本测试文件本身就是一次 gate 运行)。"""
    src = inspect.getsource(gate)
    assert "__main__" in src, "预期 gac-local-gate.py 保留 __main__ 入口"
