# KOS 迁移影响分析 & 全局 MCP 审计

> 日期: 2026-05-20 | 迁移: `kos/` → `kos/`

---

## 一、本机所有 Agent CLI 及 MCP 配置

| Agent | 配置文件 | MCP 数量 | 涉及 Workspace 路径 |
|-------|----------|----------|-------------------|
| **Claude Desktop** | `~/Library/App Support/Claude/claude_desktop_config.json` | 4 (kos, MCP_DOCKER, ai-toolbox, mcp_installer) | ✅ **kos** → `Workspace/kos/kos-mcp-server.py` |
| **Claude-3p (三方版)** | `~/Library/App Support/Claude-3p/claude_desktop_config.json` | 4 (kos, MCP_DOCKER, ai-toolbox, mcp_installer) | ✅ **kos** → **iCloud 路径** (`iCloud~md~obsidian/.../tools/kos`) — 不影响 Workspace 迁移 |
| **hermes (eCOS Agent CLI)** | `~/.hermes/config.yaml` | 6 (kos, minerva, wps-note-cloud, sharedbrain, wps-office, agora) | ✅ **kos/minerva/wps-office/agora** — 全部绝对路径到 Workspace，**kos 会断** |
| **OpenCode (Claude Code)** | `~/.config/opencode/opencode.json` | 6+ | ❌ 无 |
| **Cursor** | `~/.cursor/mcp.json` | 2 | ❌ 无 |
| **GitHub Copilot** | `~/.github/copilot/mcp.json` | 1 | ❌ 无 |
| **Windsurf** | — | 未安装 | — |
| **Cline/Continue** | — | 未安装 | — |

> **hermes 是第二个也是最重要的入口**，它把 kos/minerva/agora/wps-office 全部作为 MCP 注册了。

---

## 二、KOS 迁移 — 所有需要改的东西

### 🔴 运行时必须改 (6 处 — 不改就断)

| # | 位置 | 当前内容 | 改法 |
|---|------|----------|------|
| 1 | **Claude Desktop MCP** | `"args": ["/Users/.../kos/kos-mcp-server.py"]` | `kos` → `kos` |
| 2 | **hermes config.yaml** | `kos` MCP 指向 `/Users/.../kos/kos-mcp-server.py` | `kos` → `kos` |
| 3 | **~/.zshrc L83** | `export KOS_HOME=/Users/.../kos` | 更新路径 |
| 4 | **~/.zshrc L84** | 同上 **重复行** | 删掉去重 |
| 5 | **eCOS integrate_pipeline.py:102** | `sys.path.insert(0, '{ECOS}/../kos')` | 验证后修复或删 |
| 6 | **eCOS WF-001-kos-daily-index** | cron 工作流通过 KOS_HOME 调 kos | 更新 env 即可 |

> **Claude-3p 的 kos MCP 走 iCloud 路径**，与 Workspace 各自独立，**不用改**。

### 🟡 文档路径引用 (20+ 处 — 不影响运行但应改)

| 来源 | 数量 | 说明 |
|------|------|------|
| `DigitalBrainOS/docs/*.md` | ~12 处 | 架构蓝图/适配器注册/审查报告 |
| `eCOS/LADS/*.md` | ~6 处 | 交接文档/失败报告 |
| `eCOS/AGENTS.md` | 1 处 | Agent 导航 |
| `eCOS/README.md` | 1 处 | 项目说明 |
| `kos/README.md` | 1 处 | 自身文档 |
| `SharedBrain/` JSON 报告 | 2 处 | 运行时快照 |
| `agora/docs/*` | ~2 处 | MCP 代理架构/用户指南 |

### 🟢 安全 — 只写了 `kos` 项目名

`CLAUDE.md`、`INVENTORY.md`、`AUDIT.md`、`DigitalBrainOS/README.md` 等中的项目表格项。

---

## 三、环境变量现状

```
~/.zshrc:
  L83: export KOS_HOME=/Users/xiamingxing/Workspace/kos
  L84: export KOS_HOME=/Users/xiamingxing/Workspace/kos  ← 完全重复

实际有两个 KOS 相关环境变量:
  KOS_HOME  — kos 数据目录 (被 kos 自身脚本读取)
  KOS_SRC / KOS_DST  — 迁移工具 (kos/migrate.py)
```

---

## 四、定时任务审计

| 来源 | 存在？ | 引用 kos？ |
|------|--------|-----------|
| 系统 crontab (`crontab -l`) | ❌ 无 | — |
| launchd agent | ❌ 无 | — |
| systemd timer | ❌ 无 (macOS) | — |
| **eCOS 内部调度器** | ✅ 有 | ✅ WF-001 每日 02:00 调 kos 索引 (通过 KOS_HOME) |
| hermes (eCOS agent CLI) | 已安装 | 通过 env 调用，不直接引用路径 |

---

## 五、结论

**影响面极窄。** 全局 4 个 Agent CLI 中只有 Claude Desktop 引用了 Workspace 路径。真要改的运行时位置一共 **4 处** (Claude Desktop + .zshrc ×2 + eCOS 脚本)，文档可批量替换。

要不要现在就做？
