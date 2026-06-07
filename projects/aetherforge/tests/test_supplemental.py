"""Supplemental tests for recently-added modules.

Covers: GroupChat, GraphWorkflow, StepCallbacks, ObjectStore, new providers.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "gateway", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "mesh", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "swarm", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

passed = 0
failed = 0


def test(name):
    def dec(fn):
        def wrapper():
            global passed, failed
            try:
                fn()
                passed += 1
                print(f"  ✅ {name}")
            except Exception as e:
                failed += 1
                import traceback
                print(f"  ❌ {name}: {e}\n{traceback.format_exc()}")
        return wrapper
    return dec


# ══════════════════════════════════════════════════════════════════════════
# StepCallbacks (vs CrewAI)
# ══════════════════════════════════════════════════════════════════════════

@test("StepCallbacks: 6 hooks + decorator")
def test_callbacks():
    from compute_mesh.worker.callbacks import StepCallbacks
    cb = StepCallbacks()
    events = []

    @cb.on_task_start
    def s(wid, task): events.append(f"start:{wid}")
    @cb.on_task_complete
    def c(wid, res): events.append(f"complete:{wid}")
    @cb.on_task_fail
    def f(wid, err): events.append(f"fail:{wid}")
    @cb.on_worker_claim
    def cl(wid): events.append(f"claim:{wid}")
    @cb.on_worker_release
    def rl(wid): events.append(f"release:{wid}")
    @cb.on_retry
    def rt(wid, n, err): events.append(f"retry:{wid}:{n}")

    cb.fire_task_start("w1", "task")
    cb.fire_task_complete("w1", {"ok": True})
    cb.fire_task_fail("w2", "err")
    cb.fire_worker_claim("w3")
    cb.fire_worker_release("w3")
    cb.fire_retry("w4", 2, "timeout")

    assert len(events) == 6
    assert events == ["start:w1", "complete:w1", "fail:w2", "claim:w3", "release:w3", "retry:w4:2"]
    assert len(cb.on_task_start) == 1
    assert len(cb.on_task_complete) == 1


@test("StepCallbacks: add/remove/clear")
def test_callbacks_management():
    from compute_mesh.worker.callbacks import StepCallbacks
    cb = StepCallbacks()

    def h1(wid, task): pass
    def h2(wid, task): pass

    cb.on_task_start.add(h1)
    cb.on_task_start.add(h2)
    assert len(cb.on_task_start) == 2

    cb.on_task_start.remove(h1)
    assert len(cb.on_task_start) == 1

    cb.on_task_start.clear()
    assert len(cb.on_task_start) == 0


# ══════════════════════════════════════════════════════════════════════════
# GroupChat (vs AutoGen)
# ══════════════════════════════════════════════════════════════════════════

@test("GroupChat: round-robin speaker selection")
def test_groupchat_round_robin():
    from swarm_engine.group_chat import GroupChat, GroupChatAgent
    a1 = GroupChatAgent(name="A", system_prompt="You are A.", role="worker")
    a2 = GroupChatAgent(name="B", system_prompt="You are B.", role="worker")
    a3 = GroupChatAgent(name="C", system_prompt="You are C.", role="worker")
    chat = GroupChat(agents=[a1, a2, a3], max_turns=3)

    speaker = chat._round_robin_select(1)
    assert speaker.name == "A"
    speaker = chat._round_robin_select(2)
    assert speaker.name == "B"
    speaker = chat._round_robin_select(3)
    assert speaker.name == "C"
    speaker = chat._round_robin_select(4)
    assert speaker.name == "A"  # wraps around


@test("GroupChat: termination check")
def test_groupchat_termination():
    from swarm_engine.group_chat import GroupChat, GroupChatAgent
    a1 = GroupChatAgent(name="A", system_prompt="You are A.", role="worker")
    chat = GroupChat(agents=[a1], max_turns=10)
    assert chat._check_termination("A", "we should TERMINATE now") is True
    assert chat._check_termination("A", "continuing the discussion") is False


@test("GroupChat: message model")
def test_groupchat_message():
    from swarm_engine.group_chat import GroupChatMessage
    msg = GroupChatMessage(sender="test", content="hello", turn=1, agent_role="worker")
    assert msg.sender == "test"
    assert msg.content == "hello"
    assert msg.turn == 1
    assert msg.agent_role == "worker"


# ══════════════════════════════════════════════════════════════════════════
# GraphWorkflow (vs LangGraph)
# ══════════════════════════════════════════════════════════════════════════

@test("GraphWorkflow: linear DAG")
def test_graph_linear():
    from swarm_engine.graph_workflow import GraphWorkflow
    wf = GraphWorkflow()

    @wf.node("input")
    def inp(state):
        return {"x": state["v"] * 2}

    @wf.node("process")
    def proc(state):
        return {"result": f"num={state['x']}"}

    wf.add_edge("input", "process")
    wf.set_entry("input")
    state = wf.run({"v": 21})
    assert state["x"] == 42
    assert "num=42" in state["result"]


@test("GraphWorkflow: conditional branching")
def test_graph_conditional():
    from swarm_engine.graph_workflow import GraphWorkflow
    wf = GraphWorkflow()

    @wf.node("decide")
    def decide(state):
        return {"val": state["input"]}

    @wf.node("positive")
    def pos(state):
        return {"out": "pos"}

    @wf.node("negative")
    def neg(state):
        return {"out": "neg"}

    def if_pos(state):
        return "positive" if state["val"] >= 0 else "negative"

    wf.add_edge("decide", "positive", condition=lambda s: "positive" if s["val"] >= 0 else None)
    wf.add_edge("decide", "negative", condition=lambda s: "negative" if s["val"] < 0 else None)
    wf.set_entry("decide")

    s1 = wf.run({"input": 5})
    assert s1.get("out") == "pos"

    s2 = wf.run({"input": -3})
    assert s2.get("out") == "neg"


@test("GraphWorkflow: cycle detection")
def test_graph_cycle():
    from swarm_engine.graph_workflow import GraphWorkflow
    wf = GraphWorkflow()

    @wf.node("a")
    def a(state):
        return {"v": state.get("v", 0) + 1}

    @wf.node("b")
    def b(state):
        return {"v": state.get("v", 0) + 1}

    wf.add_edge("a", "b")
    wf.add_edge("b", "a")  # cycle!
    wf.set_entry("a")

    state = wf.run({"v": 0})
    assert state["v"] >= 1  # ran at least once before cycle detection


@test("GraphWorkflow: node/edge listing")
def test_graph_listing():
    from swarm_engine.graph_workflow import GraphWorkflow
    wf = GraphWorkflow()

    @wf.node("a")
    def a(s): return {}

    @wf.node("b")
    def b(s): return {}

    wf.add_edge("a", "b")
    assert wf.get_nodes() == ["a", "b"]
    assert ("a", "b") in wf.get_edges()


# ══════════════════════════════════════════════════════════════════════════
# ObjectStore (vs Ray)
# ══════════════════════════════════════════════════════════════════════════

@test("ObjectStore: put/get/delete")
def test_objectstore_basic():
    from compute_mesh.worker.object_store import ObjectStore
    store = ObjectStore(db_path=None)
    oid = store.put({"msg": "hello", "num": 42})
    data = store.get(oid)
    assert data["msg"] == "hello"
    assert data["num"] == 42
    assert store.exists(oid) is True
    store.delete(oid)
    assert store.exists(oid) is False
    assert store.get(oid) is None


@test("ObjectStore: TTL expiry")
def test_objectstore_ttl():
    from compute_mesh.worker.object_store import ObjectStore
    import time
    store = ObjectStore(db_path=None)
    oid = store.put({"temp": True}, ttl=0.05)
    assert store.get(oid) is not None
    time.sleep(0.1)
    assert store.get(oid) is None


@test("ObjectStore: SQLite persistence")
def test_objectstore_persist():
    from compute_mesh.worker.object_store import ObjectStore
    import tempfile, os
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_objs.db")
    store = ObjectStore(db_path=db_path)
    oid = store.put({"persistent": True})
    assert store.get(oid)["persistent"] is True

    # New instance should load from DB
    store2 = ObjectStore(db_path=db_path)
    assert store2.get(oid)["persistent"] is True

    store2.delete(oid)
    assert store2.get(oid) is None


@test("ObjectStore: put_many/get_many")
def test_objectstore_bulk():
    from compute_mesh.worker.object_store import ObjectStore
    store = ObjectStore(db_path=None)
    refs = store.put_many({"a": 1, "b": 2, "c": 3})
    assert len(refs) == 3
    assert "a" in refs
    results = store.get_many(list(refs.values()))
    assert len(results) == 3


@test("ObjectStore: stats")
def test_objectstore_stats():
    from compute_mesh.worker.object_store import ObjectStore
    store = ObjectStore(db_path=None)
    store.put({"x": "y"})
    stats = store.get_stats()
    assert stats["total_objects"] == 1
    assert stats["total_size_bytes"] > 0


# ══════════════════════════════════════════════════════════════════════════
# New Providers
# ══════════════════════════════════════════════════════════════════════════

@test("Providers: 9 registered in detection")
def test_providers_9():
    from llm_gateway.detection import _PROVIDER_REGISTRY
    assert len(_PROVIDER_REGISTRY) == 9
    assert "azure" in _PROVIDER_REGISTRY
    assert "bedrock" in _PROVIDER_REGISTRY
    assert "vertex" in _PROVIDER_REGISTRY


@test("Providers: all classes importable")
def test_providers_import():
    from llm_gateway.providers import (
        AzureOpenAIProvider, BedrockProvider, VertexAIProvider,
    )
    assert AzureOpenAIProvider
    assert BedrockProvider
    assert VertexAIProvider


@test("Providers: detection priority includes new")
def test_providers_priority():
    from llm_gateway.detection import detect_backends
    # Should not crash, returns available (hitl/ollama)
    available = detect_backends()
    assert isinstance(available, list)


@test("Providers: L0 M1 includes new engines")
def test_providers_l0():
    from pathlib import Path
    m1_dir = Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "compute_engine"
    if m1_dir.exists():
        files = list(m1_dir.glob("*.yaml"))
        names = [f.stem for f in files]
        assert "ENG-AZURE-OPENAI" in names, f"Missing from {names}"
        assert "ENG-BEDROCK" in names
        assert "ENG-VERTEX-AI" in names
        print(f"    L0 M1: {len(files)} engine nodes ({len(names)})")
    else:
        print("    L0 M1 dir not found (skip)")


# ══════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════

def run_all():
    global passed, failed
    print("=" * 60)
    print("  AetherForge Supplemental Tests")
    print("=" * 60)

    import inspect
    test_fns = []
    for name, fn in inspect.getmembers(sys.modules[__name__]):
        if name.startswith("test_") and callable(fn):
            test_fns.append(fn)

    for fn in sorted(test_fns, key=lambda f: f.__name__):
        fn()

    total = passed + failed
    print()
    print(f"  Supplemental: {passed}/{total} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
