---
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y2Q1-T6-02
created: 2026-09-07
status: accepted
lifecycle: contract
owner: governance-agent
last-reviewed: 2026-09-07
---

# Spec: 知识层统一归并首期 — bos://memory/unified 统一接口与 adapter 去重

## Motivation

知识层存在双头重叠（gbrain + kairon 占全系 51% 代码）。kairon 为 Python 多包 monorepo（16 packages，
含 kos/kronos/eidos/minerva/mos 等记忆相关包），gbrain 为 TypeScript 项目（323K 行 TS，含
retrieval/hybrid.ts 混合检索）。多个包各自实现 vector/embedding/search/recall adapter，与
`kairon/packages/mos`（MOS 内核，ADR-0372 control plane）重复。T6-02 首期将统一记忆存取
路由到 MOS，消除重复 adapter。

## 关键事实（D1 真理验证，2026-09-07）

- **MOS 实际位置**：`projects/knowledge/kairon/packages/mos/`（pyproject name=`mos`，4.3K 行，
  含 `MemoryOS` 类 write/recall/KnowledgeRef + routing.py intent classify/RRF fuse）
- **gbrain 是纯 TypeScript**（0 py / 1316 ts，323K 行），`src/retrieval/hybrid.ts` 仅 108 行
- **kairon 记忆相关包**：kos（29.6K 行）、minerva（23.3K 行）、eidos（12.6K 行）、kronos（3.4K 行）、
  mos（3.3K 行 src）
- **台账原 write_surface `projects/mos/` 不存在**（过时路径），修正为 `projects/knowledge/kairon/packages/mos/`

## 变更

1. **`bos://memory/unified` 统一接口**（`kairon/packages/mos/src/mos/unified.py`）
   - `unified_write(scope, payload)` / `unified_recall(query, filters)` / `unified_search(query, limit)`
   - 内部路由到 MemoryOS + backends_for_intent（复用现有 routing.py 的 intent classify + RRF fuse）
   - 注册 BOS 路由 `bos://memory/unified/*`（在 omo_bos_seeds 或 metaos_bus_adapter 暴露）

2. **kairon 内 adapter 去重**（同语言 Python，安全归并面）
   - 审计 kos/kronos/eidos 的 vector/embedding/search adapter，删除与 mos/adapters 重复的实现，
     改为 import mos 统一入口
   - 目标归并（删除/去重）≥ 10,000 LOC 重复适配层与假实现

3. **gbrain 侧仅路由接入**（跨语言，不做代码删除——留后续期）
   - `bos://memory/gbrain/*` → unified 统一入口的调用方契约对齐
   - 不改 gbrain TS 代码本体

4. **测试**：`kairon/packages/mos/tests/test_unified_memory.py`（verify 命令 `mos.test_unified_memory`）
   - unified_write/recall/search 单测 + 路由到 backend 的集成测试

## 验收（done_when 映射）

- ✅ 新政策入库时……（本 bet 无政策场景，映射为 unified_write 幂等 + 去重写入）
- ✅ 检索召回优先最新有效依据（unified_recall 走 MemoryOS 最新优先语义）
- ✅ 记忆冲突检测率 100%（unified_write 写前冲突检测，复用 mos 现有语义）

verify:
- `uv run python -m mos.test_unified_memory` exit 0
- `make gac-local-gate` exit 0

## 非目标（non_goals 映射）

- 不物理删除 gbrain TS 代码（跨语言归并留后续期）
- 不删除 kairon/gbrain 已有有效测试用例（test_loc 只增不减）
- 不改历史架构决策 ADR

## 风险与 circuit_breaker

- 风险：adapter 去重可能破坏现有检索路径 → 原有知识检索测试失败时**立即阻断代码删除并回滚**
  （circuit_breaker 原语）
- 风险：unified 接口与现有 bos://memory/mos/* 语义冲突 → 只新增 bos://memory/unified 命名空间，
  不改既有 mos 语义
- 面积：新增 `unified.py`（~200 行）+ `test_unified_memory.py`（~250 行），删除重复 adapter ≥10K LOC
