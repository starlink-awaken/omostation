---
title: ADR-0002-tiered-cache
type: doc
---

# ADR-0002: 三级缓存架构

> 状态: 接受 | 日期: 2026-07-08

## 背景

搜索延迟需 <100ms 以满足 AI Agent 实时性要求, 但向量 embedding 计算慢 (本地 ~7ms, omlx ~174ms), 全量检索无法满足延迟目标。

## 决策

采用 **L1 内存 LRU + L2 SQLite 持久化 + L3 冷检索** 三级缓存架构, 热查询延迟 <1ms。

## 技术细节

### 缓存层次

| 层级 | 存储 | 容量 | TTL | 延迟 |
|------|------|------|-----|------|
| L1 | 内存 OrderedDict | 1000 条 | 5 min | <0.1ms |
| L2 | SQLite search_cache 表 | 无限制 | 1 hour | <10ms |
| L3 | 实际检索 | — | — | <100ms |

### 缓存 Key
```
MD5(query.lower().strip() + ":" + mode + ":" + limit)
```

### 写入策略
1. 实际检索完成后, 仅缓存有结果的查询
2. 同时写入 L1 (热缓存) 和 L2 (持久缓存)
3. L3 → L2 命中时自动提升至 L1

### 失效策略
- L1: LRU 淘汰 + TTL 过期
- L2: TTL 过期 + 表级清理
- 查询变更时: 同 key 自动覆盖

### Token 预算控制
```
中文: ~1.5 char/token
英文: ~3.5 char/token
混合: 动态估算
```

## 后果

### 正面
- 热查询延迟: <1ms (提升 100x)
- 温查询延迟: <10ms
- 减少向量 embedding 计算量

### 负面
- 缓存一致性需维护
- L1 内存占用 (~10MB)
- 首次查询仍慢 (冷启动)

## 参考

- Cache Replacement Policies: LRU, LFU, ARC
- Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
