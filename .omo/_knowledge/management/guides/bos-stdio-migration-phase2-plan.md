---
last_updated: 2026-08-25
---

# BOS stdio 迁移 Phase 2 实施方案

> 日期: 2026-08-01
> 阶段: Phase 2 (高频服务)
> 状态: 规划中

## 1. 目标

迁移 30 个高频 stdio 服务到 mcp_proxy 或 inline。

## 2. 候选服务

### 2.1 高频服务（基于调用频率估算）

| # | URI | 包名 | 域 | 优先级 |
|---|-----|------|-----|--------|
| 1 | bos://memory/kos/search | kos | memory | P0 |
| 2 | bos://memory/kos/ingest | kos | memory | P0 |
| 3 | bos://memory/kos/schema | kos | memory | P1 |
| 4 | bos://governance/metaos/decide | metaos | governance | P0 |
| 5 | bos://governance/metaos/immune | metaos | governance | P0 |
| 6 | bos://governance/metaos/route | metaos | governance | P1 |
| 7 | bos://governance/omo/state | omo | governance | P0 |
| 8 | bos://governance/omo/debt | omo | governance | P1 |
| 9 | bos://governance/agent-workflow/bootstrap | agent-workflow | governance | P1 |
| 10 | bos://governance/agent-workflow/verify-plan | agent-workflow | governance | P1 |
| 11 | bos://governance/agent-workflow/observe | agent-workflow | governance | P1 |
| 12 | bos://governance/agent-workflow/compliance | agent-workflow | governance | P1 |
| 13 | bos://governance/agent-workflow/doctor | agent-workflow | governance | P1 |
| 14 | bos://governance/evolution/status | governance-evolution | governance | P2 |
| 15 | bos://governance/evolution/validate | governance-evolution | governance | P2 |
| 16 | bos://governance/evolution/traces | governance-evolution | governance | P2 |
| 17 | bos://governance/evolution/golden-paths | governance-evolution | governance | P2 |
| 18 | bos://governance/evolution/packages | governance-evolution | governance | P2 |
| 19 | bos://memory/kronos/ingest | kronos | memory | P1 |
| 20 | bos://memory/kronos/scan | kronos | memory | P1 |

### 2.2 迁移方式

| 方式 | 适用场景 | 优势 | 劣势 |
|------|----------|------|------|
| mcp_proxy | 有独立 MCP Server | 进程复用，延迟低 | 需要管理进程 |
| inline | 简单函数调用 | 零延迟，类型安全 | 耦合度高 |
| internal | 内部模块引用 | 零延迟 | 需要重构代码 |

## 3. 实施计划

### 3.1 Phase 2a: 高频服务迁移（1周）

**目标**: 迁移 10 个 P0 高频服务

**步骤**:
1. 分析服务依赖关系
2. 选择迁移方式（mcp_proxy vs inline）
3. 实施迁移
4. 测试验证

### 3.2 Phase 2b: 中频服务迁移（2周）

**目标**: 迁移 20 个 P1/P2 服务

**步骤**:
1. 批量分析服务
2. 自动化迁移脚本
3. 测试验证
4. 监控指标

## 4. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 服务依赖复杂 | 中 | 高 | 依赖分析工具 |
| 性能回归 | 低 | 中 | 性能基准测试 |
| 配置错误 | 中 | 中 | 配置验证脚本 |

## 5. 成功标准

- [ ] 30 个服务迁移到 mcp_proxy 或 inline
- [ ] 所有服务端点可达
- [ ] 延迟增加 < 100ms
- [ ] 无功能回归
