---
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 双机雷雳 5 算力织网双向备份与断网容灾自愈
bet_id: BET-Y1Q3-T10-119
status: accepted
lifecycle: contract
owner: ml-platform
created: 2026-09-03
last-reviewed: 2026-09-03
---

# 双机雷雳 5 算力织网双向备份与断网容灾自愈

## Intent

在 `omlxc.daemon.dma_daemon.DMADaemonController` (ADR-0437) 物理层基础上, 新增
`projects/omlxc/src/omlxc/dataplane/failover.py` 高层故障转移控制器:
1. **心跳状态机**: 监听 `MeshTelemetrySnapshot.is_connected`, 触发 P0/P1 故障转移
2. **请求接管**: 双机争夺 inference job 时, winner-takes-all (避免脑裂), 记录 audit
3. **10 秒降级目标**: 拔插雷雳 5 → fallback to 14B local single-node → 业务无中断
4. **3 秒重连**: 重连后 3 秒内恢复 120Gbps P2P 状态同步 + 双机工作模式
5. **Audit log**: 每次故障转移写 `.omo/state/failover-audit.jsonl` 含时间 + 状态 + 接管者

## Contract

- `projects/omlxc/src/omlxc/dataplane/failover.py`: 新增. `FailoverController` 类 + `start()` / `stop()` / `request_takeover()` 公开方法
- `projects/omlxc/tests/integration/test_dual_node_failover.py`: 5 个集成测试 (注入断网/重连/争抢/审计/超时)
- `tests/test_failover_controller.py`: 7 个单元测试 (心跳状态机/降级/重连/争抢 winner-takes-all/审计/超时降级/circuit-breaker)
- `.omo/_knowledge/retros/BET-Y1Q3-T10-119.md`: 复盘 (4 lessons)
- `docs/reports/2026-09-03-t10-119-failover-validation.md`: 验证报告

## Non-goals

- 不实现真物理 DMA (由 DMA daemon 负责, failover 仅观察 + 决策)
- 不依赖外部公有云
- 不修改 DMA daemon 内部行为 (只读 telemetry)

## Risks

- **R1 脑裂**: 双机同时认为自己是 primary 导致数据冲突. 解决: 单写者租约 (lease), 5s 内续约, 不续则降级
- **R2 误降级**: 短暂网络抖动触发频繁降级. 解决: 5s 滑动窗口, 连续 3 次心跳失败才降级
- **R3 审计日志膨胀**: 每次都写盘, 长期可能 GB 级. 解决: 滚动归档 (>1MB 自动压缩)

## Circuit Breaker

- 双机心跳丢失 >15s → 强制切断 DMA 共享内存写入, 自动降级 local

## Verify

- `python3 -m pytest projects/omlxc/tests/integration/test_dual_node_failover.py -v` 期望 5/5 PASS
- `python3 -m pytest tests/test_failover_controller.py -v` 期望 7/7 PASS
- `make gac-local-gate` 期望全绿
- 注入断网 fixture: 模拟 link down → failover 应 10s 内触发 → 重连后 3s 内恢复
