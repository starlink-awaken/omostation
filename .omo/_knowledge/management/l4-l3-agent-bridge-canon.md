---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# L4 → L3 → Agent 桥接协议 (Architecture Canon)

> 2026-06-06 · 固化为 5+3+1 架构宪章 · 不允变更

---

## 核心认知

```
L4 自我层 ─ 被动 · 数据面 · 存"要做什么"和"为什么做"
    │
    │ 被读取 (通过 L3 MCP 工具, 不直接暴露)
    │
L3 入口层 ─ 主动 · 工具面 · 存"怎么做"的路径
    │
    │ Agent 通过 L3 MCP 获取 L4 上下文
    │
Agent ── 执行器 (人或 AI) · 读 L4 上下文, 决定调哪些 L3→I0→L2 工具
```

## 为什么不是独立 P0 层

P0 产品表面层在 4+1+3 架构中定义为独立层 (hermes-console/pallas/gstack/bos-skill-cli)。
四组件全缺失, 架构审计评为 F。

5+3+1 不再设独立 P0 层: **产品表面 = L3 cockpit + L4 数据 + Agent 桥接**。

## L3 → L4 桥接 MCP 工具 (规划)

所有 MCP 工具在 cockpit 实现, L4 自身不暴露 MCP:

| 工具 | L4 数据源 | 返回 |
|------|----------|------|
| `workspace_context` | CARDS + .omo | 活跃目标/阶段/约束聚合 |
| `cards_status` | CARDS SQLite | 按优先级排序的卡片列表 |
| `cards_check` | CARDS | 操作约束合规性检查 |
| `vault_search` | Vault Markdown | 关键词检索知识 |

## L4 自身协议

- **CARDS 协议**: SQLite schema (`cards` 表: id/title/status/priority/domain/created/closed) + frontmatter Markdown 文件
- **Vault 协议**: `1-active/2-knowledge/3-archive` 三层结构 + frontmatter metadata
- **约束协议**: `.omo/governance-constraints.yaml` 定义 Agent 行为边界

## Agent 执行闭环

```
① workspace_context → 知: 当前目标/约束/阶段
② cards_check → 审: 操作是否合规
③ Agora → kairon/minerva/ecos → 行: 执行变更
④ cards_update → 归: 记录结果/进度/新债务
⑤ vault 写入 → 记: 沉淀新知识
```

## 不变项

- L4 永远不跑代码 (不部署 MCP server, 不成为运行时)
- L3 永远是 L4 的唯一程序化入口
- Agent 永远通过 Agora (I0) 调用任何下层服务
