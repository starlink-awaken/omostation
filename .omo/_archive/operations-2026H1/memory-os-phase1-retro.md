---
lifecycle: history
owner: engineering-team
last_updated: 2026-08-04
related:
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ./memory-os-adapter-audit.md
  - ../architecture/memory-os.md
title: Memory OS Phase 1 — 复盘与迭代
type: doc
---

# Memory OS Phase 1 — 复盘与迭代

## 本轮交付

| 项 | 结果 |
|----|------|
| `packages/mos` write/recall/status | shipped + 16 pytest |
| Dual-track raw+theta | 真写 InMemory 后端；theta fail 保留 raw |
| Envelope validation | `mos.envelope.validate_envelope` |
| Intent routing + RRF | `file_note` / `preference_self` / `code_structure` 等 |
| BOS | `bos://memory/mos/{write,recall,status}` in agora |
| Card events | emit memory URI；indexer dual-accept + dual-subscribe |
| Staged commits | kairon mos → cockpit events → agora BOS → root pointers/docs |

## 中途迭代修复

1. **`RecallResult.count` 缺失** — 测试访问 `r.count` 失败；补 `@property count`（不改测试去迁就半残 API）。
2. **Indexer 订阅测试** — 双 pattern 后 last-body 断言失效；改为 capture 全部 subscribe 调用并断言 memory+brain 均在。

## 诚实缺口（P2+）

- Live KOS/gbrain 后端端口未接（当前 InMemory + CLI fixture；BOS stdio 调 CLI）
- Mem0 仍 stub/off；forget / consolidate 未实现
- OMO raw 仍进程内 InMemoryRawBackend，非 omo broker 生产落盘
- Graphiti / multi-agent ACL / cockpit UI 明确未做
- eidos 未再包一层 Envelope（校验在 mos 内，避免循环依赖）

> **后续 supersede（勿当现状）**: ACL/RBAC/Neo4j/UI/CLI/BOS 六 URI 已在 Phase 5–8 + #978 分批落地。本文件保留 Phase 1 当时边界；现状见 `docs/architecture/memory-os.md` 与 `.omo/_truth/registry/memory-os.yaml`。

## 经验

- 控制面与 I/O 分离使 dual-track 可测且不依赖 Qdrant/Neo4j
- 事件迁移必须 dual-accept **一 release**，否则会静默丢索引
- 子模块 main 直推 + root pointer 分 commit，避免与主仓脏 worktree 混写

## 验证证据

- `{SCRATCH}/mos-pytest.log` — 16 passed
- `{SCRATCH}/cockpit-indexer-pytest.log` — 9 passed
- `{SCRATCH}/mos-gate.log` — scoped gate / structural checks
