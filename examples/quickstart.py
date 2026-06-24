"""蜂群式AI超级大脑 — 使用示例

展示核心功能的完整使用方式。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def example_state_sync():
    """示例 1: 多节点状态同步"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    print("=== 示例 1: 多节点状态同步 ===")

    node_a = StateSyncService("node-a", SyncStrategy.EVENTUAL)
    node_b = StateSyncService("node-b", SyncStrategy.EVENTUAL)

    node_a.set("config", "production")
    node_a.set("database_host", "192.168.1.10")

    snap_a = node_a.generate_snapshot()
    node_b.sync_from_snapshot(snap_a)

    print(f"  node-a: {node_a.get_all()}")
    print(f"  node-b: {node_b.get_all()}")
    print()


def example_dag_scheduler():
    """示例 2: DAG 任务调度"""
    from ecos.l0.governance import TaskScheduler, DAGScheduler

    print("=== 示例 2: DAG 任务调度 ===")

    ts = TaskScheduler()
    dag = DAGScheduler(ts)

    ts.submit_task("design", "系统设计", priority=10)
    ts.submit_task("implement", "实现功能", priority=9)
    ts.submit_task("test", "测试验证", priority=8)
    ts.submit_task("deploy", "部署上线", priority=7)

    dag.add_dependency("implement", "design")
    dag.add_dependency("test", "implement")
    dag.add_dependency("deploy", "test")

    order = dag.get_topological_order()
    critical = dag.get_critical_path()
    plan = dag.get_execution_plan()

    print(f"  拓扑排序: {' → '.join(order)}")
    print(f"  关键路径: {' → '.join(critical)}")
    print(f"  并行计划: {len(plan)} 轮")
    print()


def example_collective_decision():
    """示例 3: 蜂群集体决策"""
    from ecos.l0.governance import CollectiveDecision, DecisionMethod

    print("=== 示例 3: 蜂群集体决策 ===")

    cd = CollectiveDecision()
    cd.create_proposal(
        "p1",
        "选择部署策略",
        ["canary", "blue-green", "rolling"],
        DecisionMethod.MAJORITY_VOTE,
    )

    cd.vote("p1", "agent-1", "canary")
    cd.vote("p1", "agent-2", "canary")
    cd.vote("p1", "agent-3", "canary")
    cd.vote("p1", "agent-4", "blue-green")
    cd.vote("p1", "agent-5", "rolling")

    result = cd.decide("p1")
    print(f"  投票结果: {result}")

    tally = cd.tally_votes("p1")
    for option, info in tally.get("tally", {}).items():
        print(f"    {option}: {info['count']} 票")
    print()


def example_knowledge_graph():
    """示例 4: 知识图谱"""
    from ecos.l0.governance import KnowledgeGraphBuilder

    print("=== 示例 4: 知识图谱 ===")

    kg = KnowledgeGraphBuilder()
    kg.add_node("python", {"type": "language"})
    kg.add_node("ml", {"type": "field"})
    kg.add_node("dl", {"type": "field"})
    kg.add_node("data", {"type": "field"})

    kg.add_edge("python", "ml", "prerequisite")
    kg.add_edge("python", "dl", "prerequisite")
    kg.add_edge("python", "data", "prerequisite")
    kg.add_edge("ml", "dl", "related")

    pr = kg.pagerank()
    dc = kg.degree_centrality()
    communities = kg.find_communities()

    print(f"  PageRank: {', '.join(f'{k}={v:.3f}' for k, v in sorted(pr.items()))}")
    print(f"  度中心性: {', '.join(f'{k}={v:.3f}' for k, v in sorted(dc.items()))}")
    print(f"  社区数: {len(communities)}")
    print()


def example_recommendation():
    """示例 5: 知识推荐"""
    from ecos.l0.governance import (
        PersonalKnowledgeManager,
        KnowledgeNode,
        KnowledgeType,
        PreferenceEngine,
        RecommendationEngine,
    )

    print("=== 示例 5: 知识推荐 ===")

    km = PersonalKnowledgeManager()
    pe = PreferenceEngine()

    docs = [
        ("ai-basics", "AI fundamentals", ["ai", "basics"]),
        ("ml-algorithms", "Machine learning algorithms", ["ml", "algorithms"]),
        ("dl-networks", "Deep learning neural networks", ["dl", "networks"]),
        ("cooking", "Cooking recipes", ["cooking", "recipes"]),
    ]

    for doc_id, text, tags in docs:
        km.add_knowledge(
            KnowledgeNode(
                node_id=doc_id,
                knowledge_type=KnowledgeType.FACT,
                content={"text": text},
                tags=tags,
            )
        )

    pe.learn("user-1", "ai", "topic", 5.0)
    pe.learn("user-1", "ml", "topic", 3.0)

    engine = RecommendationEngine(km, pe)
    recs = engine.recommend("user-1", limit=3)

    print("  推荐结果:")
    for r in recs:
        print(f"    {r.node_id}: score={r.score:.3f} ({r.reason})")
    print()


def example_role_switching():
    """示例 6: 角色切换"""
    from ecos.l0.governance import RoleManager, RoleDefinition, RoleType, RoleSwitcher

    print("=== 示例 6: 角色切换 ===")

    rm = RoleManager()
    rm.define_role(
        RoleDefinition(
            role_id="worker",
            role_type=RoleType.WORKER,
            capabilities=["code"],
            constraints={},
        )
    )
    rm.define_role(
        RoleDefinition(
            role_id="reviewer",
            role_type=RoleType.SPECIALIST,
            capabilities=["review"],
            constraints={},
        )
    )
    rm.define_role(
        RoleDefinition(
            role_id="lead",
            role_type=RoleType.COORDINATOR,
            capabilities=["manage"],
            constraints={},
        )
    )

    rm.assign_role("alice", "worker")

    switcher = RoleSwitcher(rm, cooldown_seconds=0)
    switcher.set_prerequisites("lead", ["worker"])

    ok, msg = switcher.switch("alice", "reviewer")
    print(f"  切换: worker → reviewer = {ok} ({msg})")

    ok, msg = switcher.switch("alice", "lead")
    print(f"  切换: reviewer → lead = {ok} ({msg})")

    history = switcher.get_switch_history("alice")
    print(f"  切换历史: {len(history)} 次")
    print()


def example_fault_tolerance():
    """示例 7: 故障容错"""
    from ecos.l0.governance import FailoverManager, FailoverRule, FailoverStrategy

    print("=== 示例 7: 故障容错 ===")

    fm = FailoverManager()
    fm.add_rule(
        FailoverRule(
            "r1",
            "primary",
            ["secondary-1", "secondary-2", "secondary-3"],
            FailoverStrategy.ROUND_ROBIN,
        )
    )

    targets = []
    for i in range(6):
        target = fm.execute_failover("primary")
        targets.append(target)

    print(f"  故障转移序列: {targets}")
    print(
        f"  轮询验证: {'正确' if targets == ['secondary-1', 'secondary-2', 'secondary-3', 'secondary-1', 'secondary-2', 'secondary-3'] else '异常'}"
    )
    print()


def example_load_balancing():
    """示例 8: 负载均衡"""
    from ecos.l0.governance import LoadBalancer, LoadBalancingStrategy

    print("=== 示例 8: 负载均衡 ===")

    lb = LoadBalancer(LoadBalancingStrategy.LEAST_CONNECTIONS)
    lb.register_node("server-1", weight=1)
    lb.register_node("server-2", weight=2)
    lb.register_node("server-3", weight=1)

    lb.update_connections("server-1", 10)
    lb.update_connections("server-2", 3)
    lb.update_connections("server-3", 7)

    selected = lb.select_node()
    print(f"  最少连接选择: {selected}")
    print()


def main():
    """运行所有示例"""
    print("=" * 60)
    print("蜂群式AI超级大脑 — 使用示例")
    print("=" * 60)
    print()

    example_state_sync()
    example_dag_scheduler()
    example_collective_decision()
    example_knowledge_graph()
    example_recommendation()
    example_role_switching()
    example_fault_tolerance()
    example_load_balancing()

    print("=" * 60)
    print("所有示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
