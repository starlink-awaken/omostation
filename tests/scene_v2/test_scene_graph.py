"""Integration tests for scene-graph.py."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENE_GRAPH = ROOT / "bin" / "ssot" / "scene-graph.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCENE_GRAPH), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_validate():
    """Graph validation should pass (no cycles)."""
    r = run("validate")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["valid"] is True
    assert data["cycles_detected"] == 0
    assert data["nodes"] >= 3


def test_build():
    """Graph build should produce valid DAG."""
    r = run("build")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "entry_point" in data
    assert "topological_order" in data
    assert "nodes" in data
    assert len(data["topological_order"]) == len(data["nodes"])


def test_execute_dry_run():
    """Graph execution should traverse all reachable nodes."""
    r = run("execute", "--dry-run")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["scenes_executed"] >= 1
    assert "results" in data
    assert "correlation_id" in data


def test_entry_point_is_root():
    """Entry point must be a root node (no inbound edges) and be reachable in topo order.

    NOTE: 图是多根森林 (实测 69 节点中 69 个入边为 0), 故 `topological_sort` 的
    Kahn+字母序实现不保证 entry 排首位 —— 首位取的是字母序最小的根, 而
    `entry_point` 是设计上的**执行入口**, 二者语义不同 (此前断言
    `topological_order[0] == entry_point` 属错误假设)。
    正确不变量: ① 拓扑序覆盖全部节点; ② entry 出现在拓扑序中;
    ③ entry 无入边 (root); ④ 拓扑序满足所有边的方向约束。
    """
    r = run("build")
    data = json.loads(r.stdout)
    entry = data["entry_point"]
    order = data["topological_order"]
    nodes = data["nodes"]

    # ① 覆盖全部节点
    assert sorted(order) == sorted(nodes)
    # ② entry 在拓扑序中
    assert entry in order
    # ③ entry 无入边 (root)
    inbound = {n: 0 for n in nodes}
    for node in nodes.values():
        for edge in node.get("edges", []):
            inbound[edge["target"]] = inbound.get(edge["target"], 0) + 1
    assert inbound[entry] == 0, f"entry {entry} has {inbound[entry]} inbound edge(s)"
    # ④ 拓扑序约束: 每条边的 source 必须排在 target 之前
    position = {node: idx for idx, node in enumerate(order)}
    for source, node in nodes.items():
        for edge in node.get("edges", []):
            assert position[source] < position[edge["target"]], (
                f"topological order violated: {source} -> {edge['target']}"
            )


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
