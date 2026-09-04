---
title: README
type: doc
---

# Iris — Connector Hub for Personal Knowledge Platforms

统一连接器中心，对接多个个人知识平台（Notion、Obsidian、飞书等）。

## CLI

```bash
iris --help                    # 查看所有命令
iris list                      # 列出连接器或内容
iris search <query>            # 跨平台搜索
iris sync                      # 触发拉取同步
iris status                    # 连接器健康状态
```

## MCP

```bash
iris-mcp                       # 启动 FastMCP stdio 服务
```

MCP 工具: `iris_list_connectors`, `iris_search`, `iris_sync`, `iris_validate` 等。
