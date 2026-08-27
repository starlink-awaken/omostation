---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Hermes 研究过程记录

> 2026-05-31 对 workspace 内所有 hermes 相关内容的全面探索与深度阅读。
>
> 作为 hermes-convergence-strategy.md 的原始研究笔记，包含工具记录和关键发现。

---

## 源文件发现清单

### 命名含 "hermes" 的文件（19 个）

| # | 文件路径 | 重要性 |
|---|----------|--------|
| 1 | `.hermes/hermes-agent/deep-audit-ecosystem-cli-inactive.md` | 核心 — Hermes agent CLI 生态深度审计 |
| 2 | `.hermes/adapters/identity_middleware.py` | 核心 — 身份中间件适配器 |
| 3 | `.omo/plans/archive/hermes-ops-design.md` | 设计 — 统一运维中心 MCP 服务 |
| 4 | `.omo/task-prompts/phase7-t100-hermes-taskobject.md` | 设计 — Hermes 集成 TaskObject |
| 5 | `projects/agentmesh/src/hermes/routes.ts` | 核心 — Gateway Hermes 路由 |
| 6 | `projects/agentmesh/packages/gateway/src/hermes/routes.ts` | 核心 — 同上（gateway 包版本） |
| 7 | `projects/kairon/packages/agent-runtime/scripts/install-hermes-bridge.sh` | 关键 — 脚本桥接安装 |
| 8 | `projects/SharedBrain/scripts/install-hermes-bridge.sh` | 关键 — 同上 |
| 9 | `projects/_archived/wksp/scripts/install-hermes-bridge.sh` | 归档 — 同上 |
| 10 | `projects/_archived/iris/scripts/install-hermes-bridge.sh` | 归档 — 同上 |
| 11 | `projects/_archived/eCOS/scripts/install-hermes-bridge.sh` | 归档 — 同上 |
| 12 | `projects/_archived/legacy-readme-snapshots/agora/scripts/install-hermes-bridge.sh` | 归档 — 同上 |
| 13 | `projects/_archived/agent-runtime/scripts/install-hermes-bridge.sh` | 归档 — 同上 |
| 14 | `projects/_archived/Forge/scripts/install-hermes-bridge.sh` | 归档 — 同上 |
| 15 | `projects/_archived/legacy-readme-snapshots/hermes-webui/docs/why-hermes.md` | 文档 — 716 行上游文档 |
| 16 | `projects/_archived/legacy-readme-snapshots/hermes-webui/docs/rfcs/hermes-run-adapter-contract.md` | 设计 — 949 行 RFC |
| 17 | `projects/_archived/legacy-readme-snapshots/hermes-webui/scripts/wsl/hermes_webui_autostart.sh` | 归档 — WSL 自动启动 |
| 18 | `projects/_archived/legacy-readme-snapshots/hermes-webui/tests/test_issue2023_hermes_home_skill_modules.py` | 归档 — 测试文件 |
| 19 | `projects/_archived/eCOS/wpsnote-index/525765530785_Hermes 知识库选型深度指南：从 qmd 到 bge-m3，本地 RAG 全栈性能拆解.md` | 参考 — 知识库选型 |

### 内容含 "hermes" 的非命名文件（关键部分）

| # | 文件路径 | 发现 |
|---|----------|------|
| 1 | `projects/kairon/packages/agent-runtime/src/agent_runtime/engine.py` | API key 回退链含 Hermes |
| 2 | `projects/kairon/packages/agent-runtime/src/agent_runtime/tools.py` | 沙箱白名单含 `.hermes` |
| 3 | `projects/kairon/packages/agent-runtime/src/agent_runtime/config.py` | ALLOWED_PATHS 含 `.hermes` |
| 4 | `projects/kairon/packages/agent-runtime/src/agent_runtime/mcp_server.py` | MCP Server 供 Hermes 调用 |
| 5 | `projects/kairon/packages/cron-service/src/cron_service/mcp_server.py` | 注释标记 Hermes 集成 |
| 6 | `projects/kairon/packages/cron-service/src/cron_service/executor.py` | 脚本解析优先查 `~/.hermes/scripts/` |
| 7 | `projects/kairon/packages/ecos/src/ecos/cli/scheduler.py` | eCOS 调度 → Hermes kanban |
| 8 | `projects/kairon/packages/agora/src/agora/registry.yaml` | 注册了 hermes-ops 服务 |
| 9 | `projects/kairon/packages/agora/src/agora/federation.py` | AgentCard 含 agent:hermes |
| 10 | `projects/gbrain/src/commands/serve.ts` | SIGHUP 来自 hermes-agent restart |
| 11 | `.omo/MASTER-BLUEPRINT.md` | P0 用户入口层 |
| 12 | `.omo/standards/ARCHITECTURE_CONVERGENCE.md` | 收敛路线规划 |
| 13 | `.omo/_knowledge/design/task-center-requirements.md` | 179 条断裂 symlink |

---

## 关键架构发现

### 1. Hermes 四重角色

| 角色 | 健康度 | 说明 |
|------|--------|------|
| 用户入口 | ✅ 正常 | WeChat/IM 推送路径 |
| 调度引擎 | ❌ 断裂 | 179 symlink 断裂 |
| 记忆系统 | ✅ 正常 | OMO 无替代实现 |
| MCP 工具源 | ⚠️ 重叠 | 与 agent-runtime 重叠 |

### 2. 核心矛盾

```
Hermes 最强大的能力（分层记忆 + 自改进技能）也是 OMO 最缺的能力
Hermes 最脆弱的部分（断裂 symlink + 调度碎片化）却是 OMO 正在构建的部分
```

### 3. Adapter Contract 哲学

> "the adapter should be a protocol translator, not a runtime surrogate"
> "WebUI is thin in execution ownership, not thin in product scope"

---

## 已创建文档

- `hermes-convergence-strategy.md` — 正式收敛策略文档，主推荐方向 A + 方向 B 参考
- 本文件 — 研究过程记录（附文件清单和关键发现）

---

*维护: 2026-05-31*
