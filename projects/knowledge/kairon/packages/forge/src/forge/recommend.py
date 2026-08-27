import json
import sys

sys.path.insert(0, "src")
from forge.forge_config import GRAPH, REGISTRY  # type: ignore[import-not-found]

g = json.loads(GRAPH.read_text())
reg = json.loads(REGISTRY.read_text())


def rec_by_tool(tid: str) -> None:
    nodes = g["nodes"]
    tn = [n for n in nodes if n["id"] == tid and n["type"] == "Tool"]
    if not tn:
        tn = [n for n in nodes if n["type"] == "Tool" and tid in n["id"]]
    if not tn:
        return print("未知")
    t = tn[0]
    aids = set()
    for e in g["edges"]:
        if e["source"] == t["id"]:
            aids.add(e["target"])
        elif e["target"] == t["id"]:
            aids.add(e["source"])
    bt: dict[str, list[dict]] = {}
    for n in nodes:
        if n["id"] in aids:
            bt.setdefault(n["type"], []).append(n)
    print()
    print("推荐 (基于:", t["label"], ")")
    print()
    for t, lb in [
        ("Tool", "你可能还需要"),
        ("Knowledge", "相关知识"),
        ("Skill", "可搭配技能"),
        ("Capability", "关联能力"),
    ]:
        its = bt.get(t, [])
        if its:
            print(" ", lb, ":")
            for n in its[:5]:
                print("   ", n["id"], "-", n["label"][:60])
            print()
    print("  共", len(aids), "个关联节点")


def rec_freq() -> None:
    tu = [
        (t, t.get("telemetry", {}).get("use_count", 0))
        for t in reg["tools"]
        if t.get("telemetry", {}).get("use_count", 0) > 0
    ]
    tu.sort(key=lambda x: -x[1])
    if not tu:
        return print("暂无使用数据")
    print()
    print("推荐 (基于使用频率)")
    print()
    for t, c in tu[:5]:
        print(" ", t["id"], "(%d次使用)" % c)  # noqa: UP031
        aids = set()
        for e in g["edges"]:
            if e["source"] == t["id"]:
                aids.add(e["target"])
            elif e["target"] == t["id"]:
                aids.add(e["source"])
        rn = [n for n in g["nodes"] if n["id"] in aids and n["type"] in ("Skill", "Knowledge")]
        for n in rn[:3]:
            print("   |->", n["type"], ":", n["label"][:50])
        print()


args = sys.argv[1:]
if "--tool" in args:
    rec_by_tool(args[args.index("--tool") + 1])
elif "--gap" in args:
    # reuse existing recommend_by_gap from the file
    from recommend import recommend_by_gap  # type: ignore[import-not-found]

    recommend_by_gap(args[args.index("--gap") + 1])
elif "--frequent" in args:
    rec_freq()
else:
    print("用法: python3 src/recommend.py --tool <id> [--gap <名称>] [--frequent]")
