# ADR — Phase 11 Wave 4 — KOS Canonical MetaType Calibration

> Historical ADR reference. It records the decision made in that wave; current runtime status and current implementation ownership must be verified from the codebase and current SSOT surfaces.

## Context

KOS CLI 已公开 `domain/fact/document/relation/inference/state/constraint/processor` 这组 MetaType 过滤语义，但 ingest 入库阶段此前只会写入 `document/constraint/unknown`，导致用户可见过滤面和真实存储语义不一致。

## Decision

引入一份集中式的 KOS MetaType SSOT：

- `kos.meta_types.CANONICAL_META_TYPES`
- `kos.meta_types.FILTERABLE_META_TYPES`
- `kos.meta_types.infer_meta_type(...)`

并将这份定义同时用于：

1. ingest 入库时的 `metadata_json.meta_type` 赋值
2. CLI `list/search --meta-type` 的帮助与可见枚举

当前校准采用 **kind + source path** 的 additive 推断方式，不改变既有文档存储结构。

## Consequences

1. KOS 的存储语义与 CLI 暴露的 MetaType 过滤面重新对齐。
2. `fact / inference / constraint / processor` 等类型首次能稳定写入索引元数据，而不再被压扁成 `document/unknown`。
3. 后续如果要把 MetaType 进一步与 Eidos/SharedBrain 做深度统一，可以继续在这份集中式枚举上演进，而不必再分散修改 ingest 和 CLI。
