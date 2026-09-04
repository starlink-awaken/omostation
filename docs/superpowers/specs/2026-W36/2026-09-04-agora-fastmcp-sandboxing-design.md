---
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Agora FastMCP 工具生态全域自动化测试与动态沙箱权限隔离
bet_id: BET-Y1Q4-T8-01
status: accepted
lifecycle: contract
owner: agora-team
created: 2026-09-04
last_updated: 2026-09-04
---

# Agora FastMCP 工具生态全域自动化测试与动态沙箱权限隔离

## Intent

为 Agora 注册的 40+ 个 BOS 服务与 FastMCP 工具建立完备的契约测试套件,
引入基于 Capability 标签的只读/隔离写/外发沙箱权限系统, 杜绝外部 Agent 非法越权.

## Contract

- `projects/agora/src/agora/server/sandboxing.py`: 新增. 3 级沙箱隔离 + @sandbox decorator
- `projects/agora/tests/unit/test_bos_sandboxing.py`: 新增. 9 个单元测试
- `.omo/_knowledge/retros/BET-Y1Q4-T8-01.md`: 复盘 (5 lessons)

## 3 级沙箱

| Level | 权限 | 典型工具 |
|-------|------|----------|
| READ_ONLY | 只读状态查询 | bos_inbox_search, bos_spine_status |
| ISOLATED_WRITE | 本地状态写入 | bos_inbox_draft, bos_spine_draft |
| EXTERNAL_SEND | 外发网络请求 | bos_spine_sign, bos_mesh_dma_status |

## Non-goals

- 不降低本地已授权 Agent 的正常调用吞吐
- 不引入 Kafka/RabbitMQ 等外部 MQ
- 不实现分布式事件总线 (单进程 asyncio)

## Risks

- **R1 装饰器性能**: @sandbox 增加 <1ms 开销. 解决: 纯 dict lookup + 无 I/O
- **R2 40+ 工具 schema 合规**: 需遍历 tools_bos/ 子包. 解决: future work
- **R3 沙箱未接入实际工具**: V1 是独立模块. 解决: 后续接入时加 @sandbox

## Circuit Breaker

- 沙箱准入判定 > 5ms → 快速放行 + 告警

## Verify

- `python3 -m pytest projects/agora/tests/unit/test_bos_sandboxing.py` 期望 9/9 PASS
- `make gac-local-gate` 期望全绿
