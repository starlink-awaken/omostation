# ai-tools 迁移计划

> 将 ai-tools（AI CLI Tools Manager）的能力整合到 Forge 体系

## 一、现状调查

### ai-tools 项目概览

**项目类型**: Bash+Python 混合的 AI CLI 工具管理器
**版本**: 2.0.0
**作者**: 隔壁老王
**最后更新**: 2026-02-10
**代码行数**: ~3000 行 shell + 内嵌 Python

### 核心能力

| 功能 | 文件 | 说明 |
|------|------|------|
| 统一入口 | `ai-tools.sh` (主脚本) | 单入口管理所有 AI CLI 工具 |
| 工具扫描 | `cli/core/tool-scanner.sh` | 扫描系统已安装的工具 |
| 智能路由 | `cli/core/routing-engine.sh` | 根据关键词匹配推荐工具 |
| 工具详情 | `cli/core/tool-info.sh` | 查看工具详细信息 |
| 配置管理 | `cli/core/config-wizard.sh` + `config-validator.sh` | 交互式添加/验证配置 |
| 历史记录 | `cli/core/history-manager.sh` | 追踪推荐历史 |
| 统计分析 | `cli/core/stats.sh` | 工具使用统计 |
| YAML 解析 | `cli/core/yaml-parser.sh` | YAML 配置解析 |
| 命令生成 | `cli/core/cmd-generator.sh` | 生成实际执行命令 |
| 安装/卸载 | `install.sh` / `uninstall.sh` | 一键安装部署 |

### 配置数据

- **`config/tools.yaml`**: 定义 5 个 AI 工具（openai, claude, ollama, fabric, aider）
- **`config/rules.yaml`**: 8 条路由规则（文本处理、代码编辑、本地隐私、显式指定、通用聊天、翻译、代码生成、API帮助）

### 技能文件

- `skills/SKILL.md`: Skills 入口
- `skills/Workflows/`:
  - `Route.md` — 路由工作流
  - `List.md` — 列表工作流
  - `Config.md` — 配置工作流
  - `Scan.md` — 扫描工作流

### 与 Forge 的能力重叠

| 领域 | ai-tools 有 | Forge 有 | 重叠度 |
|------|-------------|----------|--------|
| 工具注册表 | 5 个 CLI 工具 (yaml) | 120+ 工具 (json) | ⬜ 低（规模差 24x） |
| 智能路由 | 关键词 + 优先级规则 | classify.sh + MCP 推荐 | 🟡 中 |
| 使用统计 | stats.json 次数记录 | telemetry + event_log | 🟡 中 |
| 配置管理 | install.sh 部署 | forge install 部署 | 🔴 高（冗余） |
| 历史追踪 | history.json | event_log | 🟡 中 |
| 工具扫描 | which 检测 | sniff-local.sh + sniff-network.sh | 🟡 中 |
| 技能系统 | 4 个 Workflow | sediment-capture + skills 目录 | 🔴 高（冗余） |
| CI | .github/workflows/ci.yml | 无 | ➕ 可借鉴 |

## 二、迁移目标

1. **数据迁移**: 将 tools.yaml 的 5 个工具注册到 Forge tools-registry.json
2. **路由规则迁移**: 将 rules.yaml 的 8 条规则纳入 Forge classify.sh + route 体系
3. **能力去重**: 将 ai-tools 独有的能力迁移到 Forge，消除重复维护
4. **废弃处理**: 不破坏已有 install，逐步指向 Forge

## 三、迁移步骤

### Step 1: 工具数据迁移（~15min）

将 `config/tools.yaml` 的 5 个工具转换为 Forge schema v1.2 格式，追加到 `tools-registry.json`。

```json
{
  "id": "openai-cli",
  "name": "OpenAI CLI",
  "type": "tool",
  "status": "active",
  "category": ["AI", "CLI"],
  "capabilities": ["chat", "code", "analysis", "writing"],
  "access": {
    "method": "cli",
    "location": "openai",
    "config_ref": "OPENAI_API_KEY"
  },
  "source": {
    "type": "self-built",
    "provider": "OpenAI",
    "url": "https://github.com/openai/openai-cli",
    "version_tracking": true
  },
  "cost_model": "paid",
  "health": "ok",
  "notes": "Migrated from ai-tools (v2.0.0)",
  "added": "2026-05-27",
  "updated": "2026-05-27"
}
```

### Step 2: 路由规则迁移（~20min）

将 `config/rules.yaml` 的 8 条规则映射到 `classify.sh` 的方法论体系。

| ai-tools 规则 | Forge 映射 | 优先级 |
|---------------|------------|--------|
| text-processing | → `for i in category/Workflow` | P1 |
| code-editing | → `for i in category/Code` | P1 |
| local-privacy | → `for i in category/Local` | P1 |
| explicit-tool | → 工具名直接匹配 | P2 |
| general-chat | → 通用 fallback | P3 |
| translation | → 新增方法论 | P2 |
| code-generation | → `for i in category/Code` (合并) | P2 |
| api-help | → 通用 fallback | P3 |

具体做法：
1. 在 `adapters/classify.sh` 中增加来自 ai-tools 的 keyword patterns
2. 将 scoring 权重体系融入 Forge 的推荐逻辑

### Step 3: 技能文件迁移（~10min）

将 `skills/Workflows/` 下的 4 个 Markdown 文件：
- `Route.md` → 移动到 `Forge/skills/Workflows/Route.md`
- `List.md` → 移动到 `Forge/skills/Workflows/List.md`
- `Config.md` → 移动到 `Forge/skills/Workflows/Config.md`
- `Scan.md` → 移动到 `Forge/skills/Workflows/Scan.md`

并注册到 `tools-registry.json` 的 skill 类型工具中。

### Step 4: CI 借鉴（~5min）

将 `.github/workflows/ci.yml` 中的测试/验证流程借鉴到 Forge 的 verify 管线中。

### Step 5: 标记废弃（~5min）

1. 在 ai-tools 的 README.md 顶部添加弃用说明
2. 在 ai-tools 的入口脚本中添加重定向警告：`ai-tools: 此工具已废弃，请使用 forge <command>`

## 四、文件清单（待操作）

| 操作 | 源文件 | 目标 |
|------|--------|------|
| 迁移数据 | `ai-tools/config/tools.yaml` | `Forge/tools-registry.json` 新增 5 条目 |
| 迁移规则 | `ai-tools/config/rules.yaml` | `Forge/adapters/classify.sh` 增加 keyword patterns |
| 迁移技能 | `ai-tools/skills/Workflows/*.md` | `Forge/skills/Workflows/*.md` |
| 迁移 CI | `ai-tools/.github/workflows/ci.yml` | `Forge/.github/workflows/` (新建) |
| 废弃标记 | `ai-tools/README.md` | 顶部加弃用声明 |
| 废弃标记 | `ai-tools/main entry` | 加 redirect 警告 |

## 五、风险与注意事项

1. **向后兼容**: ai-tools 用户可能依赖现有的 `ai-tools` 命令，在完全迁移前需要保留兼容层
2. **路由精度差异**: ai-tools 的规则是 keywords + priority 的静态匹配，Forge 的 classify.sh 使用方法论推理，迁移时需保留 keywords 覆盖以防止退化
3. **数据独立**: ai-tools 的 history.json 和 stats.json 建议保留作为只读归档，不强制迁移到 Forge event_log

## 六、时间估算

| 步骤 | 估算时间 | 依赖 |
|------|---------|------|
| Step 1: 数据迁移 | 15min | Forge schema v1.2 |
| Step 2: 路由规则 | 20min | classify.sh 理解 |
| Step 3: 技能文件 | 10min | 无 |
| Step 4: CI 借鉴 | 5min | 无 |
| Step 5: 废弃标记 | 5min | 无 |
| **合计** | **~55min** | — |
