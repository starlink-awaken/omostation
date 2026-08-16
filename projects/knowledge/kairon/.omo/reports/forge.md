---
title: forge
type: doc
status: active
---

# 深度分析: forge

**分析日期:** 2026-06-02
**分析阶段:** Phase 3.4

## 基本信息
- 模块名: forge
- 成熟度: beta
- 版本: 1.3.0
- 责任人: null
- 描述: "个人 AI 数字资产管理中心 — 统一工具注册、发现与治理层"
- 构建系统: hatchling
- Python 版本要求: >=3.10
- CLI 入口: `forge.forge:main`

## 代码结构

### 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | 19 | 包导出 — 暴露 CLI 函数和常量 |
| `forge.py` | 738 | **核心 CLI** — 统一命令行入口, 所有命令的 dispatch 和安装器 |
| `forge_config.py` | 61 | **配置中心** — 路径常量、环境变量、CORS、反熵阈值 |
| `asset_cli.py` | 1237 | **资产清册** — v3/v4 资产注册、列表、导出、导入、监控 |
| `cron_manager.py` | 557 | **定时任务管理** — launchd plist 生成/启停、Reminders 集成 |
| `cron_utils.py` | 280 | **定时任务工具库** — plist 操作、schedule 解析、安全检查 |
| `http_api.py` | 562 | **HTTP REST API** — 资产查询、图谱查询、推荐、CSV 导出 |
| `health_check.py` | 203 | **健康巡检** — 注册表、图谱、脚本、磁盘、KOS、同步检查 |
| `entropy.py` | 323 | **反熵系统** — 候选池管理(sunrise)、日落条款(sunset)、收敛检查(converge) |
| `watchdog.py` | 254 | **看门狗守护进程** — 定时健康检查 + 状态切换通知 |
| `build_graph.py` | 166 | **图谱构建器** — 从注册表构建知识图谱 |
| `graph_utils.py` | 113 | **图谱共享工具** — kebab-case、Jaccard 相似度、图分析 |
| `graph_viz.py` | 203 | **图谱可视化** — HTML(vis-network) 和 Mermaid 输出 |
| `query_graph.py` | 104 | **图谱查询** — 关键词搜索 |
| `recommend.py` | 84 | **推荐引擎** — 基于图结构的推荐 |
| `discover_links.py` | 203 | **自动关联发现** |
| `discover_ecosystem.py` | 591 | **生态系统发现** — 发现新工具/服务 |
| `insight_report.py` | 491 | **洞察报告** — 缺口分析、周报、组合分析 |
| `sediment.py` | 391 | **沉淀管理** — capture/detect |
| `sync_registry.py` | 127 | **注册表同步** — 生成 Markdown 快照 |
| `verify.py` | 296 | **验证框架** — phase1/2/3 |
| `sniff.py` | 1 | 空文件 (仅 1 行) |
| `model_garden.py` | 58 | **模型花园** — 功能待定 |
| `entropy/healing_trigger.py` | 69 | **自愈触发器** — SharedBrain 集成 (依赖 yaml) |
| **合计** | **7131** | |

### 架构模式

- **单体 CLI + 插件式子命令**: 所有命令集中在 `forge.py`，通过 `_build_command_map()` 构建注册表
- **纯 stdlib 优先**: 除 `healing_trigger.py` 依赖 `yaml` 外，全部使用 Python 标准库
- **配置集中化**: `forge_config.py` 是唯一配置入口，消除重复定义
- **数据驱动**: 核心数据结构为 JSON 文件 (tools-registry.json, assets/registry.json, graph/graph.json)
- **macOS 深度集成**: launchd plist 管理、osascript (AppleScript)、Reminders
- **文件锁机制**: 使用 `fcntl.flock` 实现并发安全读写

### 关键模块依赖关系

```
forge.py (CLI dispatch)
  ├── forge_config.py (配置)
  ├── asset_cli.py (资产清册)
  ├── cron_manager.py (定时任务)
  │     └── cron_utils.py (plist 工具)
  ├── http_api.py (HTTP API)
  ├── health_check.py (健康检查)
  ├── watchdog.py (看门狗)
  ├── entropy.py (反熵)
  ├── build_graph.py (图谱构建)
  │     └── graph_utils.py (图工具)
  ├── graph_viz.py (可视化)
  ├── query_graph.py (图查询)
  ├── recommend.py (推荐)
  ├── discover_links.py (关联发现)
  ├── discover_ecosystem.py (生态系统)
  ├── insight_report.py (报告)
  ├── sediment.py (沉淀)
  ├── sync_registry.py (同步)
  ├── verify.py (验证)
  ├── sniff.py (空文件)
  └── model_garden.py (空模块)
```

## 依赖分析

### 内部依赖 (导入的其他 kairon 包)

**无** — 所有模块导入均为包内自引用 (`forge.forge_config`, `forge.xxx`)

### 外部依赖 (第三方库)

| 依赖 | 用途 | 位置 | 备注 |
|------|------|------|------|
| `fastmcp` | MCP 服务器 | forge.py (运行时检测) | 未声明在 pyproject.toml 中，运行时按需安装 |
| `argcomplete` | CLI 自动补全 | forge.py (可选) | 未声明，降级优雅 |
| `yaml` | 自愈规则加载 | entropy/healing_trigger.py | 唯一硬依赖 |
| `pytest` | 测试 | dev 依赖 | pyproject.toml 中声明 |

**问题**: 运行时依赖 (`fastmcp`, `yaml`) 未在 `pyproject.toml` 中声明。`fastmcp` 通过交互式安装器按需安装，但 `yaml` (PyYAML) 是 `healing_trigger.py` 的硬依赖。

### 系统依赖

- macOS launchd (plist 管理、cron 等价)
- lsof (端口检测、进程解析)
- osascript (AppleScript Reminders 管理)
- crontab (可选配置)

## 测试分析

### 测试文件

| 文件 | 相关模块 | 状态 |
|------|---------|------|
| `test_basic.py` | CLI 集成 | OK (需 forge CLI 在 PATH) |
| `test_forge.py` | forge, graph_utils, build_graph, graph_viz, http_api | OK |
| `test_asset_cli.py` | asset_cli | **ModuleNotFoundError** |
| `test_cron_utils.py` | cron_utils | **ModuleNotFoundError** |
| `test_entropy.py` | entropy | **ModuleNotFoundError** |
| `test_cron_manager.py` | cron_manager | OK |
| `test_http_api.py` | http_api | OK |
| `test_health_check.py` | health_check | OK (需验证) |
| `test_mcp_server.py` | mcp_server | 已标记 skip |
| `test_model_garden.py` | model_garden | OK (需验证) |
| `test_watchdog.py` | watchdog | OK (需验证) |

### 当前状态: 3 个 collection errors

**错误原因**: 三个测试文件 (`test_asset_cli.py:16`, `test_cron_utils.py:23`, `test_entropy.py:21`) 使用裸导入语法 `import asset_cli as m`，但所有模块位于 `forge/src/forge/` 包命名空间内。当 `sys.path` 添加 `forge/src/` 后，Python 查找的是 `src/asset_cli.py` 而非 `src/forge/asset_cli.py`。

**修复建议**:
```python
# 修改前 (test_asset_cli.py:16)
import asset_cli as m

# 修改后
import forge.asset_cli as m
```

### 覆盖率估算

- **通过测试**: 6 个文件可通过 (test_forge, test_cron_manager, test_http_api, test_basic, test_health_check, test_watchdog)
- **失败测试**: 3 个文件 ModuleNotFound
- **覆盖率**: 低 (~30%) — 25 个源文件中仅一部分有测试覆盖
- **关键未覆盖模块**: discover_ecosystem.py, discover_links.py, insight_report.py, sediment.py, sync_registry.py, verify.py, recommend.py

## 安全分析

### 潜在安全问题

1. **子进程调用 (中等风险)**:
   - `watchdog.py` 中 `subprocess.run(["curl", "-s", ...])` 包含用户输入的消息内容 — 可能导致参数注入
   - `cron_manager.py` 中 plist `ProgramArguments` 包含 `script_cmd` 拼接 — 路径校验存在但命令注入仍有风险
   - `asset_cli.py` 中 `lsof` 调用使用 f-string 拼接端口号

2. **API Token 安全 (中等风险)**:
   - `http_api.py` 使用 `FORGE_API_TOKEN` 环境变量进行 Bearer 认证
   - Token 通过环境变量传递（非文件），有进程泄漏风险
   - `--require-token` 模式下如果 `TOKEN` 为空则拒绝启动，但非强制模式默认开放

3. **CORS 配置 (低风险)**:
   - `forge_config.py` 中 `ALLOWED_CORS_ORIGINS` 默认为 `127.0.0.1:8766, localhost:8766`
   - 可通过环境变量 `FORGE_ALLOWED_ORIGINS` 覆盖 — 如设置不当可导致跨域风险

4. **注册表锁机制 (低风险)**:
   - 使用 `fcntl.flock` 实现文件锁，但部分模块（如 `entropy.py` 的 `_atomic_save`）使用了不同的写入策略
   - `http_api.py` 的 `load_registry()` 未使用文件锁

5. **healing_trigger.py (低风险)**:
   - 依赖 `urllib.request` 调用本地 Agora MCP 端点 (localhost:7422)
   - 无 SSRF 防护，但限于 localhost

### 输入验证
- **cron_utils.py**: 良好的输入验证 — 任务名正则校验、脚本名白名单、工作目录路径安全检查
- **asset_cli.py**: JSON 输入有基本字段验证，类型白名单
- **cron_manager.py**: 任务名和脚本名校验复用 cron_utils

### 敏感数据处理
- 无密码、密钥直接硬编码
- API token 通过环境变量传入（最佳实践）
- 注册表数据为本地文件，无传输加密

## 已知债务

1. **测试模块路径错误**: 3 个测试文件使用错误的导入路径 (`import asset_cli` 应为 `import forge.asset_cli`)
2. **缺失依赖声明**: `fastmcp` 和 `yaml` 未在 `pyproject.toml` 的 `dependencies` 中声明
3. **sniff.py 空文件**: `src/forge/sniff.py` 仅 1 行，功能缺失
4. **model_garden.py 空模块**: 58 行但无实际功能
5. **MCP 服务测试跳过**: `test_mcp_server.py` 被标记为 `@pytest.mark.skip`，说明 `src/mcp_server` 已合并到 `server/mcp_server.py`
6. **文件锁不一致**: 不同模块使用了不同的文件锁策略（fcntl.flock vs rename 原子写入）
7. **CLI 全集成测试跳过**: `test_basic.py` 的 3 个测试在 forge CLI 未安装时跳过
8. **http_api.py 无单元测试的 POST 端点**: `/graph/build` 和 `/insight` POST 路由未覆盖
9. **注册表文件大小限制**: `entropy.py` 和 `cron_utils.py` 各实现了 100MB 限制，但阈值值硬编码
10. **跨平台兼容性**: launchd/lsof/crontab 等 macOS 特定系统调用假定 macOS 环境

## 建议

### 短期改进 (Phase 3)
1. **修复 3 个测试导入错误**: 将 `import xxx` 改为 `import forge.xxx`，恢复测试运行
2. **声明缺失依赖**: 在 `pyproject.toml` 的 `dependencies` 中添加 `fastmcp` 和 `pyyaml`
3. **移除空文件**: 删除 `sniff.py` 的存根，确认 `model_garden.py` 的功能需求
4. **统一文件锁策略**: 确保所有注册表读写使用一致的锁机制

### 中期改进 (Phase 4)
1. **增加测试覆盖**: 为 `discover_ecosystem.py`, `discover_links.py`, `insight_report.py`, `sediment.py` 等关键模块编写测试
2. **解耦 macOS 依赖**: 将 launchctl/lsof/AppleScript 操作抽象为平台适配层
3. **API 认证强化**: 为 `http_api.py` 添加请求频率限制和 token 轮换
4. **配置中心化**: 将 `entropy.py` 和 `cron_utils.py` 中的硬编码阈值迁移到 `forge_config.py`
