---
status: active
lifecycle: history
owner: auto-fix-loop
last-reviewed: 2026-09-23
---
# Retro — BET-Y2Q2-T7-05 Cockpit-UI 全量受控路由深层访问恢复与全局命令面板索引升级

- bet: BET-Y2Q2-T7-05
- run: 20260923T033500Z-bet-execution-cockpit-ui-deep-opt
- date: 2026-09-23
- status: delivered

## 交付概要

1. **解封深层参数化业务路由**：
   - 修复 `src/components/Dashboard.tsx` 中 `<Routes>` 仅循环 `visibleRoutes` 导致所有标记为 `hidden: true` 的深层参数化页面（如 `/scenes/:id` 场景详情、`/console` 等）被通配符拦截并强制弹回首页的严重缺陷。
   - 明确将路由集合划分为 `registeredRoutes` 与 `visibleRoutes`，使 deep link 访问完全畅通，同时保持侧边栏导航条理性。
2. **全局命令面板（⌘K）索引升级**：
   - 将 `CommandPalette` 从原本受限的 38 个可见路由扩充索引至全量 48 个有效业务与控制台页面。
   - 增加业务域分类与路由路径描述，实现全局毫秒级模糊搜索直达。
3. **测试矩阵与质量证据**：
   - 78 个单元测试文件、763 项测试 100% 绿灯全部 PASS。
   - Chrome 端到端实测验证 `/scenes/test-scene` 保持原位渲染，无重定向。
   - 生产环境构建打包 314ms 完成。

## 关键度量

- 涉及文件：`src/components/Dashboard.tsx`, `src/components/dashboard-layout.css`
- 单元测试：78/78 files passed, 763 passed, 0 failed
- 路由深层访问正确率：100%
