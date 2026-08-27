---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: bos-perf-baseline-20260607.md
deprecated-since: 2026-06-23

---

# BOS URI 性能基线报告 (2026-06-07)

## 测试环境
- Python 3.13, macOS ARM64
- 单线程基准测试

## 结果

| 测试项 | 迭代 | 耗时 | 单次耗时 |
|--------|------|------|----------|
| BOSRouter resolve | 1,000 | 6.2ms | 6.2μs |
| Cache hit | 10,000 | 18.1ms | 1.8μs |
| RateLimiter acquire | 100,000 | 0.03s (30ms) | 0.3μs |
| Cache key gen (md5) | 10,000 | 12.1ms | 1.2μs |

## 吞吐量

| 组件 | 吞吐量 | 说明 |
|------|--------|------|
| BOSRouter | ~161,000 resolves/s | 100 routes 前缀匹配 |
| Cache | ~552,000 hits/s | 单条目命中 |
| RateLimiter | ~3,928,000 ops/s | 无锁路径 |
| Cache key gen | ~826,000 keys/s | md5(json) |

## 内存占用
- **BOSRouter**: 3,376 bytes (100 routes)
- **Cache**: 232 bytes (1 entry, 空存储)

## 分析

### 优势
- **RateLimiter 性能极高** (~3.9M ops/s)：适合高频调用场景，不会成为瓶颈
- **Cache 命中延迟极低** (~1.8μs)：字典查找路径优化良好
- **BOSRouter 单次解析 ~6μs**：在 100 条路由下性能充足，预计 1000 条路由也不会显著退化

### 潜在关注点
- **Cache key 生成 ~1.2μs**：md5(json.dumps) 开销可接受，但如缓存命中率低，key 生成开销可能大于缓存收益
- **BOSRouter 内存**：100 条路由 3.4KB，线性扩展下 10,000 路由约 340KB，可控
- **需补充多线程/并发场景测试**：当前仅为单线程基准，实际 Mesh 层为异步并发，GIL 影响未知

## 建议
1. BOSRouter 当前性能充足，无需优化；路由数增长至 1000+ 后重新测试
2. Cache 命中路径已优化，关注点应在淘汰策略（TTL、LRU）的正确性而非性能
3. RateLimiter 无须优化，但需验证多协程竞争场景下的公平性
4. 后续补充：并发压力测试、端到端 Mesh 转发延迟、内存泄漏长期观察
