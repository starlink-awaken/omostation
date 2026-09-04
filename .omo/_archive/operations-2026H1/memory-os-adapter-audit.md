---
lifecycle: history
owner: governance-team
last_updated: 2026-08-04
related:
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ../../.omo/_truth/registry/memory-os.yaml
title: Memory OS — 适配器与调用方审计（Phase 0）
type: doc
---

# Memory OS — 适配器与调用方审计（Phase 0）

> **目的**: 消灭「声明有双轨/Mem0 = 生产已闭环」的认知差。  
> **证据树**: `ws-memory-os-p0` @ main-aligned `work/memory-os-p0`（2026-08-04）。  
> **裁决**: ADR-0372 — 半成品不得标 production_ready。

## 1. 组件矩阵

| 组件 | 路径 | 行量级 | 生产判定 | 调用方 |
|------|------|--------|----------|--------|
| Mem0Adapter | `projects/knowledge/kairon/packages/kos/src/kos/adapters/mem0_adapter.py` | ~85 | **retired-experimental** (T3-03) | 零代码引用 (2026-08-16 全仓确认); 替代: mos mem0_shadow (default OFF) |
| MemThetaAdapter | `.../kos/adapters/memtheta_adapter.py` | ~146 | **retired-experimental** (T3-03) | 零代码引用; partial_simulation 状态已从 memory-os.yaml 移除 |
| graphiti-core | minerva optional extra | n/a | **optional_tier2** | minerva config `graphiti:`（研究路径） |
| gbrain dream/cycle | `projects/knowledge/gbrain/src/commands/dream.ts` + `core/cycle.ts` | 大型 | **production_engine** | CLI/cron/autopilot |
| card events | cockpit `api_knowledge` + `knowledge_indexer` | n/a | **live 但越域** | emit/subscribe `bos://brain/events/card_updated` |

## 2. Mem0Adapter 审计 (T3-03: 已退役标记)

> **2026-08-16 退役确认**: kos 包 `mem0_adapter.py` / `memtheta_adapter.py` 全仓零代码引用 (ingest/__init__.py 与 memory_card.py 的调用已在早前轮次移除)。保留文件仅为审计存证, 标记 experimental + 默认不加载。活替代为 `mos/adapters/mem0_shadow.py` (ADR-0372 Phase 2, `MOS_MEM0` 默认 OFF)。

### 行为

- `from mem0 import Memory` 失败 → `enabled=False`，静默 no-op
- 默认 `vector_store.provider=qdrant` host `localhost:6333`
- API 壳：`add_memory` / `search_memory` / `get_all` / `history`

### 调用方

`kos/ingest` 在文本 ingest 后：

```text
try Mem0Adapter(); if enabled: add_memory(user_id="kos-user", ...)
except: log warning
```

### 缺口

| # | 缺口 | 风险 |
|---|------|------|
| M1 | 无 feature flag SSOT | 环境偶然 enable/disable 不可复现 |
| M2 | Qdrant 非 CI 默认 | 测试与生产路径分裂 |
| M3 | user_id 固定 `kos-user` | 无 multi-scope |
| M4 | 与 gbrain facts 无同步 | 双写不同步、无 forget 传播 |
| M5 | 不经 BOS | 绕过控制面 |

### 处置（Phase 2）

迁入 `packages/mos/adapters/mem0.py`；本地可测后端优先；`default: off`；on 时须与 facts 对齐策略。

## 3. MemThetaAdapter 审计

### 行为

| 算子 | Raw | Theta（实际） |
|------|-----|----------------|
| update | `omo event emit` via **subprocess CLI** | **logger only**（注释：simulation / 未来 gbrain MCP） |
| merge | 同上 | 生成伪 `meta_*` id + log |
| filter | 同上 | **模拟** scanned/evicted 数字 |

### 调用方

`memory_card.save_card`：写 `~/.kos/memory_cards/*.md` 后 `update(confidence=0.8)`。

### 缺口

| # | 缺口 | 风险 |
|---|------|------|
| T1 | Theta 未写 gbrain | **双轨名存实亡** |
| T2 | Raw 经 subprocess CLI | 脆弱、难测、非 broker |
| T3 | filter 回报可伪造 | 运维误判 |
| T4 | 与 ADR-0315 / OMO mutation surfaces 未登记 | 治理面漂移 |

### 处置（Phase 1–2）

逻辑吸收为 `DualTrackWriter`；禁止再增加对 MemTheta 模拟路径的生产依赖；memory_card 改走 mos.write。

## 4. Graphiti

- 依赖：`minerva[tier2]` / `graphiti-core`（供应链已在 dependency baseline 讨论）
- **无** workspace 级 `bos://memory/mos` 路由
- 处置：Phase 4 场景 enable only

## 5. gbrain dream（正资产）

`runCycle` 含（非完整列表，以源码 `ALL_PHASES` 为准）：

lint → backlinks → sync → synthesize → extract → extract_facts → … → consolidate → embed → …

**裁决**: MOS `consolidate` **只编排** dream phase 子集，禁止第二引擎。

## 6. 事件域债

| 现状 | 目标 |
|------|------|
| `bos://brain/events/card_updated` | `bos://memory/events/card_updated` |

涉及：`api_knowledge.py` emit、`knowledge_indexer.py` subscribe/callback、相关 tests、SOP/AGENTS 指针。  
**兼容策略**: 一 release 双订；再删旧（ADR-0372 D5）。

## 7. 声明/执行鸿沟总结

| 声明 | 执行真相 | 优先级 |
|------|----------|--------|
| Dual-track 已实现 | Raw 部分有；Theta 模拟 | P1–P2 硬化 |
| Mem0 已集成 | 可选 no-op 壳 | P2 |
| 卡片增量索引 | **真实**（ADR-0294）但 URI 越域 | P1 迁移 |
| Sleep-time 需引入 Letta | **已有** gbrain dream | P3 产品化编排 |
| Agent 默认记忆入口 | **无** 统一 URI | P0 skill + P1 BOS |

## 8. 建议的验证探针（实施后）

```bash
# 适配器不得在 import 时抛硬错
uv run --directory projects/knowledge/kairon python -c "from kos.adapters.mem0_adapter import Mem0Adapter; print(Mem0Adapter().enabled)"

# 事件域（迁移后）
rg -n 'bos://brain/events/card_updated' projects/cockpit --glob '*.py'   # expect 0 after cleanup
rg -n 'bos://memory/events/card_updated' projects/cockpit --glob '*.py' # expect hits

# MOS（Phase 1+）
# cockpit bos resolve bos://memory/mos/recall
```

## 9. 审计结论

1. **可以依赖**: gbrain dream/cycle、ADR-0294 卡片事件管线（迁域后）、KOS/gbrain 检索后端。  
2. **不可依赖为生产闭环**: Mem0Adapter、MemTheta Theta 轨。  
3. **Phase 0 完成标准**: 本文件 + registry 与 ADR-0372 一致；无代码谎言。

## 10. Phase 1 更新（2026-08-04）

| 项 | 状态 |
|----|------|
| MOS DualTrackWriter | **真 raw+theta**（InMemory 可测路径）；不经 MemTheta 模拟 |
| Card emit | **memory** 域 canonical；indexer dual-accept |
| Mem0 / MemTheta 旧壳 | 仍非生产；新写入走 `packages/mos` |
| Live OMO/gbrain I/O | 仍 deferred（P2） |
