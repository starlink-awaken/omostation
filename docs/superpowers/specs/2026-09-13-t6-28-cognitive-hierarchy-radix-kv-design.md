---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 四级认知阶梯分级投机推理与 Radix 前缀树热缓存加速引擎设计
bet_id: BET-Y1Q4-T6-28
---


# BET-Y1Q4-T6-28: 四级认知阶梯分级投机推理与 Radix 前缀树热缓存加速引擎

## Goal

重构本地主权推理引擎（AetherForge / omlxc）：落地 L0（1B~3B 毫秒意图拦截）→ L1（7B~14B 骨干任务）→ L2（32B~70B+ 重型仲裁）的四级投机调度架构；将场景卡与核心 GaC 规约预编译为持久化 Radix 前缀树 Paged KV Cache，系统启动即常驻内存。

## Architecture

### CognitiveHierarchy (scheduler/hierarchy.py)

- **L0**: 轻量意图识别 + 护栏拦截，首字延迟 < 5ms
- **L1**: 骨干任务调度（代码生成、文档处理）
- **L2**: 重型仲裁（复杂逻辑、多步推理）
- **L3**: 降级兜底（L0~L2 全失败时）
- 级联降级：低层置信度不足时自动升级到上一层
- 防递归：最大升级深度限制，避免无限循环

### RadixPagedCache (cache/radix_paged.py)

- Radix 前缀树索引：共享前缀复用，减少重复 KV 存储
- 分页管理：Paged KV Cache，支持超长上下文
- LRU 淘汰：内存压力下自动淘汰最久未用条目
- 热加载：系统启动时预编译场景卡 + GaC 规约

### SpeculativeEngine (engine/speculative.py)

- 草稿-验证投机解码：小模型草稿 → 大模型验证
- 接受/拒绝逻辑：基于置信度阈值决定是否接受草稿
- 统计追踪：接受率、节省 token 数、延迟改善

## Non-Goals

- 不修改底层大语言模型的权重参数
- 不引入未经加密的外部云端模型端点

## Verify

- `uv run pytest projects/aetherforge/tests/test_cognitive_hierarchy.py -q` → exit 0
- `make gac-local-gate` → exit 0

## Write Surfaces

- `projects/aetherforge/src/aetherforge/scheduler/hierarchy.py`
- `projects/aetherforge/src/aetherforge/cache/radix_paged.py`
- `projects/aetherforge/src/aetherforge/engine/speculative.py`
- `projects/aetherforge/tests/test_cognitive_hierarchy.py`
