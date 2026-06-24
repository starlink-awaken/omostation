"""压力测试脚本 — 蜂群式AI超级大脑性能验证"""

import sys
import os
import time
from multiprocessing import Process, Queue

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def _worker(queue, data):
    """多进程 worker"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    node = StateSyncService("worker", SyncStrategy.EVENTUAL)
    for k, v in data.items():
        node.set(k, v)
    queue.put(node.get_all())


def bench_state_sync(n: int = 10000):
    """状态同步压力测试"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    start = time.monotonic()
    for _ in range(n):
        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        a.set("k", "v")
        snap = a.generate_snapshot()
        b = StateSyncService("b", SyncStrategy.EVENTUAL)
        b.sync_from_snapshot(snap)
    elapsed = (time.monotonic() - start) * 1000

    throughput = n / (elapsed / 1000)
    print(f"  状态同步: {n} 次, {elapsed:.1f}ms, {throughput:.0f} ops/s")
    return throughput


def bench_pagerank(nodes: int = 100, iterations: int = 20):
    """PageRank 压力测试"""
    from ecos.l0.governance import KnowledgeGraphBuilder

    kg = KnowledgeGraphBuilder()
    for i in range(nodes):
        kg.add_node(f"n{i}")
    for i in range(nodes - 1):
        kg.add_edge(f"n{i}", f"n{i + 1}", "link")
    kg.add_edge(f"n{nodes - 1}", "n0", "link")

    start = time.monotonic()
    for _ in range(100):
        kg.pagerank(iterations=iterations)
    elapsed = (time.monotonic() - start) * 1000

    throughput = 100 / (elapsed / 1000)
    print(
        f"  PageRank: {nodes}节点×{iterations}迭代×100次, {elapsed:.1f}ms, {throughput:.0f} ops/s"
    )
    return throughput


def bench_decision(n: int = 10000):
    """集体决策压力测试"""
    from ecos.l0.governance import CollectiveDecision, DecisionMethod

    cd = CollectiveDecision()
    cd.create_proposal("p1", "test", ["A", "B", "C"], DecisionMethod.MAJORITY_VOTE)
    for i in range(50):
        cd.vote("p1", f"a{i}", "A" if i < 30 else "B")

    start = time.monotonic()
    for _ in range(n):
        cd.decide("p1")
    elapsed = (time.monotonic() - start) * 1000

    throughput = n / (elapsed / 1000)
    print(f"  集体决策: {n} 次, {elapsed:.1f}ms, {throughput:.0f} ops/s")
    return throughput


def bench_multi_process(n: int = 8):
    """多进程压力测试"""

    queue = Queue()

    start = time.monotonic()
    processes = []
    for i in range(n):
        p = Process(target=_worker, args=(queue, {f"k{j}": j for j in range(100)}))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    results = []
    while not queue.empty():
        results.append(queue.get())

    elapsed = (time.monotonic() - start) * 1000

    print(f"  多进程: {n}进程×100键, {elapsed:.1f}ms, {len(results)}/{n} 成功")
    return elapsed


def main():
    print("=" * 60)
    print("蜂群式AI超级大脑 — 压力测试")
    print("=" * 60)
    print()

    print("【性能基准】")
    t1 = bench_state_sync(10000)
    t2 = bench_pagerank(100, 20)
    t3 = bench_decision(10000)

    print()
    print("【压力测试】")
    t4 = bench_multi_process(8)

    print()
    print("=" * 60)
    print("总结:")
    print(f"  状态同步: {t1:.0f} ops/s")
    print(f"  PageRank: {t2:.0f} ops/s")
    print(f"  集体决策: {t3:.0f} ops/s")
    print(f"  多进程: {t4:.1f}ms")
    print("=" * 60)


if __name__ == "__main__":
    main()
