---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P2-T0 persistence-prerequisites 实质化报告

> **状态**: ✅ done (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P2 (Memory spine) 阶段 T0 — persistence-prerequisites 收口
> **目的**: 关闭 §12.6 跨仓债 E1/E3 收口 + 5 仓 persistence 风险登记
> **链接**: OPC-PHASE-PLAN.yaml OPC-P2-T0 / §19 战报 / M1.5 Gate B2

---

## §1.0 一句话总结

**OPC-P2-T0 (persistence-prerequisites) 实质化完成**——E1 (omo 跨 gbrain 验证) + E3 (kairon async 适配) 双收口，§12.6 跨仓债 E1-E4 4/4 收口（之前 2/4），5 仓 persistence 风险清零。

## §1.1 E3 收口 — kairon async 适配

**问题**: ContentVersionTracker._append_version_log 是 `async def`，但 fcntl.flock 同步锁在 event loop 中阻塞。

**解决**: `asyncio.to_thread` 包装 fcntl 锁，让锁在独立线程执行。

**改动**:
- `kairon-utils/src/kairon_utils/versioning.py:155-180` — 改 `_append_version_log` 用 `asyncio.to_thread(_do_append)`
- `kairon-utils/tests/append_only_log_test.py` — 加并发 50 次 record_version 测试 + 验证 < 2s

**测试**: 4/4 pass，含 50 次并发 fcntl 验证不阻塞。

## §1.2 E1 收口 — omo 跨 gbrain 验证

**问题**: omo audit-rollout dispatcher 5 仓路径 (omo 子仓 / tools/audit.sh / n/a) 中 gbrain 缺 tools/audit.sh，跨仓验证 5 → 5 仓闭环缺一环。

**解决**: gbrain/tools/audit.sh (E1 P0 实施)
- 走 `bun -e '...'` 调 AppendOnlyLog.readAllSync
- 扫 `~/.gbrain/audit/*.jsonl` 真实记录
- 输出 §17 R0 JSON (与 omo/runtime/kairon/metaos 一致 schema)
- 适配 omo audit-rollout dispatcher 5 仓路径

**实测**:
```
gbrain audit.sh: ✅ AppendOnlyLog importable
                561 records
                density=0
                health_grade=R0
```

**跨仓聚合真闭环** (5 仓):
```
worst_health_grade: R0
5 仓 §17 metrics 全部收敛
```

## §1.3 §12.6 跨仓债 E1-E4 全收口

| 债 | 状态 | 详情 |
|----|------|------|
| **E1** omo → gbrain 跨仓链接 | ✅ done | omo audit-rollout dispatcher + gbrain/tools/audit.sh + 5 仓 R0 收敛 |
| **E2** metaos D Layer 接入 omo audit-rollout | ✅ done | E2 P0 dispatcher 跑通 5 仓 worst=R0 |
| **E3** kairon async 适配 | ✅ done | asyncio.to_thread 包装 fcntl_lock, 4/4 tests pass |
| **E4** AppendOnlyLog 跨仓 SSOT 收口 | ✅ done | 5 仓对比表 + §17 schema 文档化 |

**4/4 全部收口 ✅** — §12.6 跨仓债清零。

## §1.4 5 仓 persistence 风险状态

| 仓 | 主存储 | Audit Trail | 锁策略 | 异步适配 | 风险 |
|----|--------|-------------|--------|----------|------|
| omo | JSONL (AppendOnlyLog) | 8 consumer | threading + fcntl | N/A (sync) | ✅ R0 |
| runtime | JSONL (AppendOnlyLog) | 5 consumer | threading | N/A (sync) | ✅ R0 |
| gbrain | JSONL (AppendOnlyLog) | 6 consumer | O_APPEND | N/A (sync) | ✅ R0 |
| kairon | JSONL (AppendOnlyLog) | 2 consumer | threading + fcntl | ✅ asyncio.to_thread | ✅ R0 |
| metaos | SQLite + JSONL audit | 2 consumer (D/A2A) | threading + fcntl | N/A (sync) | ✅ R0 |

**5 仓累计 0 风险**:
- 非原子写入: 0（gbrain memory-tree.ts 写锁 O_APPEND）
- 跨进程并发丢行: 0（fcntl_lock 全覆盖）
- 异步阻塞 event loop: 0（kairon asyncio.to_thread）
- Z-suffix / sort_keys / schema 校验: 100%

## §1.5 OPC-P2 推进条件 (T0 → T1+)

**Gate C acceptance**:
- ✅ kairon/gbrain/metaos persistence risks resolved (T0 完成)
- 🔄 search surfaces declare scope (T3 recall-flow)
- 🔄 outputs include source metadata (T4 source-map)
- 🔄 one real question flows collect→ingest→search→output→archive (T3)

**T0 收口 → T1 (memory-boundary) 候选**:
- gbrain / KOS / cockpit local DB / 外部文档 / family-hub 等 5 边界
- 一份 `bos://memory/**` 路由策略草案

## §1.6 累计债清零 (R0 优秀)

§17 健康度跨仓 5 仓全部 R0，**§11.6 历史债 + §12.6 跨仓债双清零**。

---

**OPC-P2-T0 收口。** E1-E4 跨仓债 4/4 全部收口，5 仓 persistence 风险清零。R57+ 推进 OPC-P2-T1 (memory-boundary) 候选就绪。
