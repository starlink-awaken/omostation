# KOS MCP Integration Guide — 知识操作系统硬件外挂指南

> **最后更新**: 2026-07-03
> **架构定义**: 将 KOS (Knowledge Operating System) 升格为 AI Agent OS 的 **「硬件外挂硬盘 (MCP Server)」**。使得外来/本地 Agent 在执行任务时，能直接用只读 SQL 或全文索引精准读取你的「驾驶舱、学习进化、卫健委公文、创意创作」等 KOS 数据资产。

---

## 🗺️ 架构设计 (Architecture)

```mermaid
graph TD
    subgraph Agent OS (Client)
        A[AI Agent / LLM CPU] <-->|JSON-RPC 2.0 via Stdin/Stdout| B[MCP Client]
    end
    
    subgraph KOS MCP Server (Hardware)
        B <--> C[bin/gac/mcp-server-kos.py]
        C <-->|Read-Only SQL| D[(kos-index.sqlite)]
        C -.->|Security Guard| E[SQL Write-Interception Regex]
    end
    
    subgraph KOS Storage Zones
        D --> Z1[@驾驶舱 / Docs]
        D --> Z2[@学习进化 / Vault]
        D --> Z3[@创意创作 / Output]
    end
```

---

## 🛠️ 提供工具清单 (Tools List)

KOS MCP Server 提供了以下四个核心硬件级 APIs：

| 工具名称 | 输入参数 (Schema) | 功能描述 |
|----------|-------------------|----------|
| `search_kos` | `query` (str), `limit` (int) | 模糊检索知识库文章、文件、项目包。 |
| `get_document` | `id` (str) 或 `path` (str) | 获取具体文档的内容预览（支持前 2000 字节正文）。 |
| `list_entities` | `limit` (int) | 列出 KOS 注册的实体模型清单（如认知框架、标准阶段）。 |
| `query_custom_sql` | `sql` (str) | **[只读限制]** 运行自定义 SQL 获取指标（如统计特定分类下的文档数）。 |

---

## 🔒 安全隔离防护 (Security Guard)

为了防范 LLM 受到恶意注入指令（Prompt Injection）执行写操作从而破坏知识库，`query_custom_sql` 实现了严格的**只读安全防线**：
1. **URI 只读加载**: 连接 SQLite 时强制附加只读属性（`file:kos-index.sqlite?mode=ro`）。
2. **敏感词正则拦截**: 任何包含 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`CREATE`、`REPLACE`、`VACUUM` 的自定义 SQL 都会被 `mcp-server-kos.py` 内部拒绝并抛出 `isError: true`，绝不在物理层面暴露任何写入权限。

---

## ⚙️ 客户端集成配置 (Client Configuration)

### 1. Claude Code 集成
在你的命令行工具中，运行以下命令一键外挂 KOS 硬盘：
```bash
claude mcp add mcp-server-kos uv -- run --with pyyaml --directory /Users/xiamingxing/Workspace python /Users/xiamingxing/Workspace/bin/mcp-server-kos.py
```

### 2. Cursor / Trae / IDE 集成
在 `IDE 设置 -> Features -> MCP` 中，添加一个全新的 MCP Server：
- **Name**: `mcp-server-kos`
- **Type**: `command`
- **Command**:
  ```bash
  /opt/homebrew/bin/uv run --with pyyaml --directory /Users/xiamingxing/Workspace python /Users/xiamingxing/Workspace/bin/mcp-server-kos.py
  ```

---

## 🚨 长效自律治理机制 (Continuous Enforcement)

为了保障 KOS 硬件服务代码的物理合规，系统建立了双层防线：
1. **TDD 测试自动化**: 创建了 `bin/ssot/test-mcp-kos.py` 脚本，自动化模拟 JSON-RPC 握手、只读查询和写操作拦截。
2. **CI 门禁守门**: `test-mcp-kos` 已经被注册在主仓 Gac Gate 门禁（`bin/gac/gac-local-gate.py`）中。每一次 commit 和 CI 运行都会拉起并执行这套协议测试，一旦发生破坏或写漏洞，门禁会立即变红阻断提交，确保自律网长久闭环。
