---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Hermes 解耦蓝图与 Roadmap

> 目标：构建可独立于 Hermes Agent 运行的个人 AI 操作系统框架。
> 当 Hermes 被移除时，系统无本质变化——所有脚本、Cron、微信推送、Agent 任务均可自主运行。

---

## 一、核心洞察

### 我们要解耦的不是代码，是运行时

我们自研的 23 个脚本已经是纯 Python，零 Hermes API 依赖。真正的依赖在**运行时基础设施**层：

| 运行时能力 | 当前谁提供 | 能否自建 |
|-----------|-----------|---------|
| **WeChat 消息发送** | Hermes Gateway (iLink) | ✅ 可——curl 调 iLink API |
| **WeChat 消息接收** | Hermes Gateway (长连接) | 🟡 可——但最复杂 |
| **LLM 对话循环** | Hermes AIAgent (run_agent.py) | ✅ 可——简化版即可满足 cron 任务 |
| **工具编排** (MCP/Terminal/File) | Hermes 内置工具 | 🟡 可——复用 MCP 客户端 |
| **Cron 调度+交付** | Hermes Cron Scheduler | ✅ 可——系统 crontab + 包装脚本 |
| **会话管理** | Hermes SessionDB | ❌ 不需要——用 KOS 替代 |
| **技能系统** | Hermes Skill 引擎 | ❌ 不需要——用工具箱替代 |

### 架构演进：收缩 Hermes 为纯执行层

```
当前: Hermes 是容器 (你的东西在它里面)
        ┌──────────────────────┐
        │ Hermes Agent        │
        │  ├─ 你的脚本         │
        │  ├─ 你的 Cron        │
        │  ├─ 你的 Memory Tree │
        │  ├─ Agora/KOS 调用  │
        │  └─ Gateway → WeChat│
        └──────────────────────┘

目标: Hermes 是工具 (你的东西在它外面)
        ┌──────────────────────┐
        │ 你的 AI OS 框架      │
        │  ├─ Workspace/eCOS   │  ← 所有脚本/知识/治理
        │  ├─ KOS/Agora/MCP    │  ← 知识存储与服务总线
        │  ├─ 自有 Cron 调度   │  ← 系统 crontab + wrapper
        │  ├─ 自有 WeChat 发送 │  ← curl iLink API
        │  └─ 自有 Agent 运行时│  ← 简化版 LLM 循环
        └──────────────────────┘
                ↕ MCP 协议
        ┌──────────────┐
        │ Hermes Agent │  ← 仅作为"可选执行器"之一
        └──────────────┘
```

---

## 二、5 层解耦架构

```
┌─────────────────────────────────────────────────────────────┐
│                    L5: 全面独立运营层                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ 12 Cron Jobs│  │  Agent Loop  │  │  Platform Gateway│  │
│  │ (系统 crontab)│  │ (自建 Agent)│  │  (微信收+发)     │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    L4: Platform Gateway                       │
│  微信消息接收 → 消息路由 → Agent 对话 → 响应发送            │
│  可降级: L4 故障时 L1-L3 继续运行                            │
├─────────────────────────────────────────────────────────────┤
│                    L3: Agent Runtime                          │
│  ┌────────────────────────────────────────────────────┐     │
│  │ agent_runner.py — 简化版 LLM 对话循环              │     │
│  │  ├─ LLM Provider Client (DeepSeek/GLM/...)         │     │
│  │  ├─ MCP Tool Orchestrator (调用KOS/Agora/Minerva) │     │
│  │  ├─ Terminal Executor (执行 shell 命令)             │     │
│  │  └─ Output Processor (结果收集+格式化)              │     │
│  └────────────────────────────────────────────────────┘     │
│  可降级: L3 故障时 L1-L2 继续运行                            │
├─────────────────────────────────────────────────────────────┤
│                    L2: Cron Scheduler                         │
│  ┌────────────────────────────────────────────────────┐     │
│  │ system crontab + cron_wrapper.sh                   │     │
│  │  ├─ no_agent 脚本 → 直接执行 → L1 交付            │     │
│  │  └─ LLM 任务 → 调用 L3 Agent Runtime → L1 交付    │     │
│  └────────────────────────────────────────────────────┘     │
│  可降级: L2 故障时 L1 的 weixin_send.py 仍可手动调用       │
├─────────────────────────────────────────────────────────────┤
│                    L1: WeChat Delivery Layer                  │
│  ┌────────────────────────────────────────────────────┐     │
│  │ weixin_send.py — 独立 WeChat 消息推送              │     │
│  │  ├─ curl 调 iLink API (复用现有 WeChat 通道)       │     │
│  │  ├─ rate limit 控制 (参考 Hermes 的限流策略)       │     │
│  │  └─ SILENT 协议支持 (空白输出不推送)                │     │
│  └────────────────────────────────────────────────────┘     │
│  最底层——纯工具层，无依赖                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、20 个 Cron Job 分类拆解

### 8 个 no_agent 脚本 → Phase 1 迁移

| # | Job | 脚本 | 周期 | 依赖 |
|---|------|------|------|------|
| 1 | eCOS Watchdog | ecos-watchdog.sh | 每5m | 纯 Bash |
| 2 | WF-011 每日摘要 | ecos-daily-digest.sh | 每天7:00 | 纯 Bash |
| 3 | ecos 研究推送 | ecos-research-push.sh | 每天10:00 | 纯 Bash |
| 4 | WF-013 知识缺口 | ecos-knowledge-gap.sh | 每天12:00 | 纯 Python |
| 5 | WF-014 WPS→KOS同步 | wpsnote-kos-sync.py | 每天1:00 | Python + curl |
| 6 | daily-todo 推送 | daily-todo.sh | 每天8:45 | 纯 Bash |
| 7 | workspace-git-sync | workspace-git-sync.py | 每天18:30 | Python |
| 8 | Hermes EventWatcher | hermes-event-watcher.py | 8-22点每5m | Python + curl |

**迁移方式**: 系统 crontab 触发 → 脚本执行 → stdout 捕获 → weixin_send.py 投递

### 11 个 Agent 任务 → Phase 2-3 迁移

| # | Job | 做了什么 | 需要的能力 |
|---|------|---------|-----------|
| 1 | WF-003 系统健康检查 | 检查 eCOS 文件完整性/Cron 状态/SSB 健康 | Terminal |
| 2 | WF-001 KOS每日索引 | 调 MCP 工具增量索引 + 系统状态 | MCP Client |
| 3 | WF-005 HANDOFF更新 | 读 STATE/HANDOFF 文件 → 更新 | File I/O |
| 4 | WF-006 感知管道 | 跑 4 个 eCOS 脚本 → 汇总 | Terminal |
| 5 | WF-002 Minerva研究 | 调 Minerva MCP 做 3 个主题研究 | MCP Client |
| 6 | WF-007 安全检查 | 跑 realtime_guard + 写入 SSB | Terminal |
| 7 | WF-008 Kanban-SSB桥接 | 跑 wf-008 脚本 | Terminal |
| 8 | WF-009 委员会周检 | 读文件 → 跑脚本 → 写入 WPS | Terminal + MCP + WPS |
| 9 | WF-010 宪法执行器 | 跑 constitution_watcher.py | Terminal |
| 10 | codexbar-quota-refresh | Python import 刷新缓存 | Python |
| 11 | wf-015-swarm-guardian | curl 调 BOS API + 监控 | curl + Terminal |

**迁移方式**: crontab 触发 → 调用 Agent Runtime → 执行 prompt → 结果投递

---

## 四、Roadmap（4 个 Phase，~5 周）

### Phase 1：WeChat 发送 + 8 个 no_agent 迁移（1 周）

**核心产出**: WeChat 发送能力独立 + 8 个 no_agent 脚本脱离 Hermes

| Task | 内容 | 估计 |
|------|------|------|
| T1.1 | `weixin_send.py` — curl 调 iLink API 发送微信消息 | 半天 |
| T1.2 | `cron_wrapper.sh` — 通用 cron 包装器（执行→捕获→SILENT判断→发送） | 半天 |
| T1.3 | 迁移 eCOS Watchdog 到系统 crontab（每5m） | 1h |
| T1.4 | 迁移 WF-011 每日摘要到系统 crontab（每天7:00） | 1h |
| T1.5 | 迁移 ecos 研究推送到系统 crontab（每天10:00） | 1h |
| T1.6 | 迁移 WF-013 知识缺口到系统 crontab（每天12:00） | 1h |
| T1.7 | 迁移 WF-014 WPS→KOS同步到系统 crontab（每天1:00） | 1h |
| T1.8 | 迁移 daily-todo 到系统 crontab（每天8:45） | 1h |
| T1.9 | 迁移 workspace-git-sync 到系统 crontab（每天18:30） | 1h |
| T1.10 | 迁移 Hermes EventWatcher 到系统 crontab（8-22点每5m） | 2h |
| T1.11 | E2E 验证：8 个脚本全部独立运行，推送正常 | 半天 |

**总计**: ~10 个任务，约 4 天

**依赖**: 无——纯脚本包装

### Phase 2：Agent Runtime 基础版（1 周）

**核心产出**: 简化的 LLM 对话循环，能跑 6 个最轻的 Agent 任务

| Task | 内容 | 估计 |
|------|------|------|
| T2.1 | `agent_runtime.py` 核心 — LLM 调用 + 工具编排循环 | 2天 |
| T2.2 | MCP Client 集成 — 连接 Agora/KOS/Minerva 工具 | 1天 |
| T2.3 | Terminal Executor — 执行 shell 命令并返回结果 | 半天 |
| T2.4 | Task 定义格式 — YAML 定义 cron prompt + 所需工具集 | 半天 |
| T2.5 | 迁移 WF-003 系统健康检查（纯文件检查） | 2h |
| T2.6 | 迁移 WF-005 HANDOFF自动更新（纯文件读写） | 2h |
| T2.7 | 迁移 WF-010 宪法执行器（跑脚本+检查输出） | 2h |
| T2.8 | 迁移 codexbar-quota-refresh（Python import + 调用） | 1h |

**总计**: ~8 个任务，约 5 天

**依赖**: Phase 1 完成（有 WeChat 发送能力）

### Phase 3：Agent Runtime 完善 + 剩余 Cron 迁移（1.5 周）

**核心产出**: 11 个 Agent 任务全部独立运行

| Task | 内容 | 估计 |
|------|------|------|
| T3.1 | Agent Runtime 完善 — MCP 工具重试、错误恢复、上下文管理 | 1天 |
| T3.2 | Agent Runtime 完善 — 技能/KB 支持（读 knowledge_base 丰富 prompt） | 1天 |
| T3.3 | 迁移 WF-006 感知管道（跑4个脚本+汇总） | 半天 |
| T3.4 | 迁移 WF-008 Kanban-SSB桥接（跑脚本） | 半天 |
| T3.5 | 迁移 WF-007 安全检查（跑脚本+写入SSB） | 半天 |
| T3.6 | 迁移 WF-001 KOS每日索引（MCP调用） | 半天 |
| T3.7 | 迁移 WF-002 Minerva研究（MCP调用） | 半天 |
| T3.8 | 迁移 WF-009 委员会周检（文件+MCP+WPS写入） | 1天 |
| T3.9 | 迁移 wf-015-swarm-guardian（curl+进程监控） | 半天 |
| T3.10 | E2E 验证：11 个 Agent 任务全部独立运行 | 1天 |

**总计**: ~10 个任务，约 7 天

**依赖**: Phase 2 完成（有 Agent Runtime 基础）

### Phase 4：平台网关 + 迁移收尾（1 周）

**核心产出**: 微信消息接收独立 + Hermes 遗留数据迁移

| Task | 内容 | 估计 |
|------|------|------|
| T4.1 | 调研 Herems Gateway WeChat 适配器代码 | 半天 |
| T4.2 | WeChat 消息接收 — webhook 或长连接（微信 iLink） | 2天 |
| T4.3 | 消息路由 — 用户消息 → Agent Runtime → 响应 | 1天 |
| T4.4 | 会话管理 — 简易 session store（SQLite） | 半天 |
| T4.5 | Skills/SKILL.md 归档 — 将现有 skills 转为知识库文档 | 1天 |
| T4.6 | 内存数据迁移 — Memory Tree DB + flat file → KOS | 半天 |
| T4.7 | 完整 E2E 验证 — 脱离 Hermes 全链路测试 | 1天 |
| T4.8 | 回滚预案文档 — 如果 L4 不稳定如何降级 | 半天 |

**总计**: ~8 个任务，约 5 天

**依赖**: Phase 3 完成

## 五、整体进度

```
Phase 1 ────── ████████████░░░░░░░░░░░░░░  4天
Phase 2 ────── ██████████████░░░░░░░░░░░░  5天  
Phase 3 ────── ██████████████████████░░░░  7天
Phase 4 ────── ████████████████░░░░░░░░░░  5天
              ───────────────────────────
Total:         ███████████████████████████  21天 (3周)

实际约 4-5 周（含验证和迭代）
```

---

## 六、关键设计决策

### 1. WeChat 发送层不依赖 Hermes

```
方案: curl -X POST -H "Authorization: Bearer $WECHAT_TOKEN" \
  -d "{\"to\":\"$USER_ID\",\"text\":\"$TEXT\"}" \
  https://ilink-api.ihome.link/v1/message/send
```

需要: WeChat iLink 的 API Key / Token（已在 Hermes gateway 配置中）。

### 2. Agent Runtime 不是 Hermes 的简化版——是专用版

Hermes AIAgent ~12k LOC 支持通用对话（人格/压缩/缓存/前端/多平台）。

我们的 Agent Runtime 只需：
- 接收一个 prompt + 可用工具列表
- 循环调用 LLM → 解析工具调用 → 执行 → 收集结果
- 输出最终结果

~500 LOC 即可覆盖 11 个 Agent cron 任务的需求。

### 3. MCP 客户端复用现有基础设施

```python
# agent_runtime.py 中
import requests, json

def call_mcp(server_url, tool_name, args):
    resp = requests.post(f"{server_url}/tools/call", json={
        "name": tool_name, "arguments": args
    })
    return resp.json()
```

Agora 已暴露 HTTP MCP 接口，KOS/Minerva 也是 MCP 服务器——无需复用 Hermes 的 MCP client。

### 4. 渐进替代，非一刀切

```
过渡状态: 
  ┌── Hermes 继续跑 LLM Agent cron ──┐
  │  + 系统 crontab 跑 no_agent 脚本  │
  └──────────────────────────────────┘
  
最终状态:
  ┌── 系统 crontab 跑所有 cron ──────┐
  │  + 自建 Agent Runtime 跑 LLM 任务 │
  │  + 自建 Gateway 收微信消息       │
  └──────────────────────────────────┘
```

---

## 七、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| WeChat iLink 接口变更 | 低 | 高 | 保持 Hermes gateway 作为备用通道 |
| Agent Runtime 无法覆盖复杂 MCP 调用 | 中 | 中 | 降级：拆复杂任务为多个简单 cron 脚本 |
| 迁移后出现 WeChat 频率限制 | 中 | 中 | 在 weixin_send.py 中内置排队/限流 |
| 忘记 Hermes 独有的技能/SKILL.md 逻辑 | 低 | 低 | 迁移前做好技能清算 |
| 系统 crontab 环境变量问题 | 中 | 低 | cron_wrapper.sh 显式 source 环境 |

---

## 八、完成标准

Phase 1 ✅ = 8 个 no_agent 脚本通过系统 crontab 独立运行，WeChat 推送正常
Phase 2 ✅ = Agent Runtime 能跑 4 个轻 Agent 任务，输出结果到 WeChat
Phase 3 ✅ = 11 个 Agent 任务全部独立运行，Hermes cron 中无活跃任务
Phase 4 ✅ = 微信消息收发不依赖 Hermes gateway，Hermes 可安全停用
全链路 E2E ✅ = 模拟 Hermes 停用 → 所有 cron 正常运行 → WeChat 推送正常
