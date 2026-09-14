# OpenHuman 分析报告 — 借鉴点与集成评估

> 来源: [tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman)
> 评估日期: 2026-05-25 | 许可证: GNU (传染性，注意)

---

## 一、OpenHuman 核心创新点

| 特性 | 描述 | 对我们的价值 |
|------|------|-------------|
| **记忆树** | 所有数据归一化为≤3k token的Markdown片段，评分折叠为层级摘要树，存SQLite+Obsidian .md | ⭐⭐⭐ 最高价值 |
| **自动拉取 (20min)** | 每20分钟遍历所有活跃连接拉取新数据 | ⭐⭐⭐ 值得借鉴 |
| **TokenJuice** | 数据接触LLM前经过压缩层(HTML→MD、去重摘要等)，最多降80%成本 | ⭐⭐⭐ 直接影响成本 |
| **118+ 一键集成** | 通过Composio连接器层，OAuth一次即可接入 | ⭐⭐ 接入模式好 |
| **模型自动路由** | 根据工作负载选推理型/快速型/视觉型模型 | ⭐⭐ 我们已有基础 |
| **记忆树+Obsidian双写** | 同时存SQLite和.md，可浏览可编辑 | ⭐⭐⭐ 补我们缺口 |

---

## 二、可直接借鉴的特性

### 借鉴 #1: 记忆树 (替代当前平面Memory MCP)

**当前**: `memory_store.json` + 关键词搜索 — 平面、无层级、不智能
**OpenHuman做法**: 所有记忆评分后折叠为层级摘要树，3k token片段，SQLite存储

**对我们**: 将Memory MCP Service (T114) 升级为层级记忆树。可参考OpenHuman的评分+折叠+摘要化机制，记忆不再是平面条目而是可导航的树。

**融合可能**: 建议`memory/mcp_server.py`增加 `memory.tree_get` 和 `memory.tree_search`，保留平面API向后兼容。

### 借鉴 #2: TokenJuice (数据压缩层)

**OpenHuman做法**: 每个tool call/web scrape/email先过压缩层：HTML→MD、URL缩短、去重摘要

**对我们**: 在Agora Router中加一个中间件层——所有MCP调用的输入/输出过压缩后再传递。可以显著降成本（8折保守估计，OpenHuman宣称80%）。

### 借鉴 #3: 自动拉取 (Auto-pull)

**OpenHuman做法**: 每20分钟遍历所有活跃连接，自动拉取新数据到记忆树

**对我们**: 现有hero cron是用户触发的、不智能。借鉴OpenHuman模式，在kronos/iris中增加定时智能拉取。

### 借鉴 #4: 记忆→Obsidian双写

**当前**: KOS知识存在SQLite中，Memory存在JSON中，不可在Obsidian中直接浏览
**OpenHuman做法**: 同时存SQLite和.md文件到Obsidian兼容目录

**对我们**: 价值较低（因为KOS自己就是索引，不依赖Obsidian），但可以增加一个`memory.export_markdown`工具把记忆导出为可浏览的.md文件。

---

## 三、License警告

OpenHuman是GNU (GPL) 许可证——**传染性**。不能直接复制代码到MIT项目中。但可以：
1. **参考理念而非代码** — 记忆树的层级结构、评分机制、压缩层等
2. **独立实现** — 我们自己写MemoryTree，不用OpenHuman的代码
3. **作为独立服务集成** — 如果OpenHuman成熟了，可以作为外部节点接入生态（通过A2A/MCP）

---

## 四、融合建议

| 借鉴点 | 融入位置 | 实现方式 | 优先级 |
|--------|---------|---------|--------|
| 记忆树 | `memory/mcp_server.py` 升级 | 独立实现(不碰GPL) | 🔴 Phase 10 |
| TokenJuice | Agora Router中间件 | 压缩层嵌入路由 | 🔴 Phase 10 |
| 自动拉取 | iris/kronos增强 | cron + 事件驱动 | 🟡 Phase 11 |
| 模型自动路由 | agentmesh Model-Orchestrator | 已有基础，增加自动分类 | 🟡 Phase 11 |
| 双写.md | memory导出工具 | 单独小工具 | 🟢 低优先级 |
