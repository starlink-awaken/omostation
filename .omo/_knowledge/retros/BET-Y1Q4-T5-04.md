---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T5-04
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-12
type: ephemeral
---

# BET-Y1Q4-T5-04 Retro — 主权连接器架构升级与统一 BOS 网关化

## What Changed
- 新增 `connector-manifest.yaml`：统一登记 16 个连接器元数据（含 15+ 种类型）
- 新增 `tools_connectors.py`：BOS 网关 MCP 工具（connector_list / connector_sync）
- 新增 `connectors_poll.py`：Resident Daemon 增量轮询器（watermark 追踪 + 状态持久化）
- 新增 `test_connectors_bos.py`：完整单元测试（manifest 验证 + 网关工具 + 轮询器）
- 追加 `bos-services.yaml`：3 条 bos://connectors/* 路由

## Key Decisions
- **统一注册表**: 所有连接器元数据收敛到 `.omo/_truth/registry/connector-manifest.yaml`，单一真值源
- **增量同步**: 基于 watermark 的增量拉取，状态持久化到 `.omo/state/connector-watermarks.json`
- **BOS 网关**: 通过 agora MCP 工具暴露 connector_list 和 connector_sync，支持过滤和 dry_run
- **Resident Daemon 集成**: connectors_poll.py 设计为可嵌入 resident daemon 的周期任务

## Verification
- `uv run pytest projects/agora/tests/test_connectors_bos.py -q` → exit 0
- 16 个连接器全部通过 manifest 结构验证
- Watermark roundtrip 序列化测试通过
- Poller dry_run 和 state persistence 测试通过

## Scope
- 6 files:
  - `.omo/_truth/registry/connector-manifest.yaml` (新)
  - `projects/agora/etc/bos-services.yaml` (追加路由)
  - `projects/agora/src/agora/server/tools_connectors.py` (新)
  - `projects/omo/src/omo/resident/connectors_poll.py` (新)
  - `projects/agora/tests/test_connectors_bos.py` (新)
  - `.omo/_knowledge/retros/BET-Y1Q4-T5-04.md` (本文件)
