# CLAUDE.md — hermes-console

> Unified UI for omostation · React 18 + TypeScript + MCP SDK
> 根工作区文档：`../CLAUDE.md`（全局）、`../AGENTS.md`（开发指南）

## 快速开始

```bash
bun install       # 安装依赖
bun run dev       # 开发服务器
bun run build     # 构建
bun test          # 运行测试
bun run lint      # TypeScript 检查
```

## 架构

```
src/
├── App.tsx                   # 主入口
├── mcp/
│   ├── client.ts             # MCP 客户端
│   └── types.ts              # MCP 类型
├── dashboard/
│   └── DashboardPage.tsx     # 仪表板
├── agent/
│   └── AgentPage.tsx         # Agent 管理
├── health/
│   └── HealthPage.tsx        # 健康检查
├── settings/
│   └── SettingsPage.tsx      # 设置
├── components/
│   ├── KnowledgeGraph.tsx    # 知识图谱可视化
│   ├── MetricsChart.tsx      # 指标图表
│   └── ServiceTopology.tsx   # 服务拓扑
├── hooks/
│   └── useMcp.ts             # MCP React Hook
└── __tests__/                # 测试
```

## 依赖

- React 18 + Vite 5
- MCP SDK (`@modelcontextprotocol/sdk`)
- TypeScript 5.3
- Vitest (测试框架)

## 关键命令

| 命令 | 说明 |
|------|------|
| `bun run dev` | 启动开发服务器 |
| `bun run build` | TypeScript 检查 + Vite 构建 |
| `bun test` | Vitest 运行 |
| `bun run lint` | `tsc --noEmit` 类型检查 |
