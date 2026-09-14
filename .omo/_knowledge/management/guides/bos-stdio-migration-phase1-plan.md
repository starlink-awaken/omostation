---
last-reviewed: 2026-08-25
type: ssot
owner: governance-team
---

# BOS stdio → mcp_proxy 迁移实施方案

> 日期: 2026-08-01
> 阶段: Phase 1 (MCP Server 服务)
> 状态: 实施中

## 1. 迁移目标

将 14 个 MCP Server 服务从 `stdio` 迁移到 `mcp_proxy` 传输方式。

### 1.1 目标服务

| # | URI | 包名 | 项目 |
|---|-----|------|------|
| 1 | bos://memory/kos/mcp-server | kos-mcp | kairon |
| 2 | bos://memory/eidos/mcp-server | eidos-mcp | kairon |
| 3 | bos://memory/ontoderive/mcp-server | ontoderive-mcp | kairon |
| 4 | bos://memory/minerva/mcp-server | minerva-mcp | kairon |
| 5 | bos://memory/kronos/mcp-server | kronos-mcp | kairon |
| 6 | bos://memory/iris/mcp-server | iris-mcp | kairon |
| 7 | bos://memory/sophia/mcp-server | sophia-mcp | kairon |
| 8 | bos://memory/forge/mcp-server | forge-mcp | aetherforge |
| 9 | bos://memory/metaos/mcp-server | metaos-mcp | metaos |
| 10 | bos://memory/ecos/mcp-server | ecos-mcp | ecos |
| 11 | bos://memory/omo/mcp-server | omo-mcp | omo |
| 12 | bos://memory/aetherforge/mcp-server | aetherforge-mcp | aetherforge |
| 13 | bos://memory/c2g/mcp-server | c2g-mcp | c2g |
| 14 | bos://capability/cockpit/mcp-server | cockpit-mcp | cockpit |

## 2. 迁移策略

### 2.1 传输方式变更

**Before (stdio)**:
```yaml
- uri: bos://memory/kos/mcp-server
  transport: stdio
  command:
  - python3
  - bin/gac/mcp-server-kos.py
```

**After (mcp_proxy)**:
```yaml
- uri: bos://memory/kos/mcp-server
  transport: mcp_proxy
  mcp_endpoint: http://localhost:8765/mcp
  description: KOS MCP Server (proxy mode)
```

### 2.2 实施步骤

1. **验证 MCP Server 端点可用性**
   - 检查每个 MCP Server 是否有 HTTP 端点
   - 验证端点是否响应 MCP 协议

2. **更新 bos-services.yaml**
   - 修改传输类型为 `mcp_proxy`
   - 添加 `mcp_endpoint` 配置
   - 保留原始 `command` 作为备用

3. **测试验证**
   - 单元测试：验证路由正确性
   - 集成测试：验证端到端调用
   - 性能测试：对比延迟和吞吐量

## 3. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| MCP Server 端点不可用 | 低 | 高 | 保留 stdio 作为备用 |
| 延迟增加 | 低 | 中 | 性能基准测试 |
| 配置错误 | 中 | 中 | 配置验证脚本 |

## 4. 回滚方案

如果迁移失败，可以快速回滚：
1. 恢复 bos-services.yaml 原始配置
2. 重启 agora 服务
3. 验证 stdio 传输恢复正常

## 5. 成功标准

- [ ] 14 个服务全部迁移到 mcp_proxy
- [ ] 所有服务端点可达
- [ ] 延迟增加 < 100ms
- [ ] 无功能回归
