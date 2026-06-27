---
status: active
lifecycle: in-progress
owner: laowang
last-reviewed: 2026-06-28
related-task: memu-engine-bpp
origin-commit: b245c11a (memu 半成品原作者)
---

# memu-engine B++ 修复进展（多会话工程）

> memu-engine.ts (b245c11a "feat: memU SQLite backend") 是半成品 — 原作者基于
> 错误类型假设写 870L, typecheck 从未通过. 用户选 B++ (完整修复), 工程量 = 数天多会话.
> 本文件记账每会话进展 + 剩余清单, 供下会话续.

## 阶段进展

### 阶段 1: import 拆分 (✅ 完成, 2026-06-28)
- memu-engine.ts 行 10-33 单 import from './types.ts' → 拆 3 块 (engine.ts + engine-types.ts + types.ts)
- 删 3 个不存在类型: LinkResult/FileUploadOpts (unused), TagRow (修 getTags 后不需要)
- 补 StaleChunkRow import (types.ts 有, 漏了)
- **结果**: memu-engine.ts 70 import 错 → 0 (但暴露 99 实现错误)

### 阶段 2: getTags 签名修复 (✅)
- getTags 返回 `Promise<TagRow[]>` → `Promise<string[]>` (匹配 BrainEngine.getTags engine.ts:399)
- 实现: SELECT tag as name 对象 → SELECT tag + map(r => r.tag) string[]

### 阶段 3: 接口边界字段名修正 (✅ 完成, 降 22 错误)
memu 作者系统性用 camelCase, gbrain 用 snake_case. 只改**接口边界**(读输入参数字段),
不动 memu 内部 SQLite schema (body/source_slug/content 列名保留一致):
- PageInput.body → compiled_truth (putPage 行 267/273)
- ChunkInput.content → chunk_text (upsertChunks 行 384)
- ChunkInput.heading/char_start/char_end → 默认 ''/0 (ChunkInput 无此字段, memu schema 多余列)
- PageFilters.prefix → slugPrefix (listPages 行 316)
- LinkBatchInput.sourceSlug/targetSlug/linkType → from_slug/to_slug/link_type (addLinksBatch)
- EngineConfig.dbPath → database_path (connect 行 55)
- CodeEdgeInput.edgeType → edge_type (行 792)
- EvalCandidateInput.toolName → tool_name (行 821)
- Link.target_slug → to_slug (行 457, getLinks 返回映射 — **待修**, 涉及接口映射)
- upsertChunks 返回 Chunk[] → void (BrainEngine 接口)
- SearchResult searchKeyword 补必需字段 (page_id/type/chunk_text/chunk_source/chunk_id/chunk_index/stale)
- ReservedConnection withReservedConnection: `fn({engine,release})` → `fn(this as unknown as ReservedConnection)`
- listStaleChunks 签名 `(_limit?)` → `(_opts?: {batchSize,afterPageId,afterChunkIndex,sourceId})`
- deleteChunks 签名 `(_ids:number[])` → `(_slug, _opts?)`

**当前 typecheck**: memu-engine.ts 99 → **77**, 总 128 → **106** (字段层清完)

## 剩余清单 (下会话续)

### 阶段 4: 53 方法签名对齐 BrainEngine (TS2416, 主障碍)
memu 用 `(src, target, opts?)` 风格, BrainEngine 用扁平参数 `(from, to, context?, linkType?, ..., opts?)` 风格.
**53 方法** (清单见 /tmp/memu_tc3.txt grep TS2416). 已知差异:
- addLink (行 412): memu 3 参 → BrainEngine 8 参 `(from, to, context?, linkType?, linkSource?, originSlug?, originField?, opts?)`
- addLinksBatch (行 420): Promise<void> → Promise<number> (返回 inserted count)
- removeLink (行 426): `(src, target, opts?)` → `(from, to, linkType?, linkSource?, opts?)`
- findByTitleFuzzy (行 441): `(title, opts?)` → `(name, dirPrefix?, minSimilarity?)` 返回 `{slug, similarity} | null`
- 其余 49 方法: 读 engine.ts BrainEngine 完整签名 + 批量对齐

**续法**: `rg "^\s+(async )?[a-z].*\(.*\).*:" src/core/engine.ts` 拿 BrainEngine 54 方法签名 → 对照 memu-engine.ts 逐方法改.

### 阶段 5: 配套文件
- src/core/memory-tree.ts (2 错误)
- src/mcp-entry.ts (2 错误)
- test/memory-tree-op.test.ts (11 错误)

### 阶段 6: 冒烟测试 (新建 test/memu-smoke.test.ts)
- createEngine({engine:'memu'}) 实例化
- connect({database_path: ':memory:'}) + initSchema
- putPage + getPage 读写一页
- addLink + getLinks
- disconnect
- 验证 memu SQLite schema 与 BrainEngine 接口行为一致

### 阶段 7: 消费方签名加 memu (doctor/embed/sync/engine-factory)
阶段 4-6 完成后, memu 真可用, 再把 memu 加回消费方类型 (当前 engine.kind 含 memu 但消费方漏).

## 风险 (已知)
- memu 作者 SQLite schema 设计意图 (body/content/source_slug 列名 vs gbrain compiled_truth/chunk_text/from_slug)
  不完全清楚 — 老克重写有曲解风险, 冒烟测试兜底
- 54 方法 SQL 逻辑从未运行验证 — typecheck 绿 ≠ 能跑
- 无原作者 (b245c11a) 设计文档 — 凭 BrainEngine 接口逆推

## Commit 策略
- **不 commit 半成品** (memu-engine.ts 还 77 错, main 保持 sync.ts wave 1 绿状态)
- 阶段 4-7 完成后 typecheck 全绿 + 冒烟测试 pass → 一次性 commit "feat: complete memu engine"
- 若中途需 checkpoint, commit 到 memu-fix 分支 (不污染 main)

## 状态
- **本会话**: 阶段 1-3 完成 (字段层清完, -22 错误). context 物理约束, 单会话无法完成阶段 4 (53 方法).
- **下会话**: 从阶段 4 续 — 读 BrainEngine 54 签名 + 批量对齐 memu 方法.

---

*memu B++ 修复进展 v1 · 2026-06-28 · 阶段 1-3 done (-22), 阶段 4-7 待续 (多会话)*
