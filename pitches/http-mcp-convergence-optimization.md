# Pitch: HTTP/MCP 收敛优化全面落实

> **Upstream**: MS-HTTP-MCP-CONVERGENCE
> **Appetite:** 2 weeks

## 背景

HTTP/MCP 收敛已基本完成（24→5 HTTP 服务，29/29 MCP stdio，0 端口冲突），但仍有以下优化空间需要全面落实：

## 优化项

### 1. 测试覆盖提升 (P0)

当前 cockpit web 模块覆盖率 81%，目标 90%+：
- app.py: 83% → 90%+
- governance.py: 76% → 85%+
- workspace_research.py: 61% → 75%+

### 2. Pre-existing 测试修复 (P1)

60 个 pre-existing 测试失败：
- agora: 40 个 bos_resolver 集成测试
- runtime: 18 个 executor/sandbox 测试
- ecos: 2 个 TCP transport 测试

### 3. 前端现代化 (P2)

dashboard.html (1011 行纯 HTML/JS) → React (hermes-console 模式)

### 4. 统一认证 (P2)

cockpit API key 管理所有子服务，避免各服务独立认证

### 5. BOS URI 网关 (P3)

cockpit 成为人类访问所有 BOS URI 的入口

### 6. 自动发现 (P3)

cockpit 启动时自动扫描注册 workspace 服务

## 验收标准

- [ ] 测试覆盖率 ≥ 90%
- [ ] pre-existing 测试失败 ≤ 10
- [ ] 前端现代化完成
- [ ] 统一认证实现
- [ ] BOS URI 网关实现
- [ ] 自动发现实现
