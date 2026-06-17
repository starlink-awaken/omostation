# 5+3+1 架构治理宪章 v1.0

> **全系统架构宪法** · 2026-06-06 · 人类审批后生效
> 本文保留治理原则与边界约束，不再维护项目计数、测试数、MCP/CLI 数、端口活跃状态、阶段完成度等运行时快照。
> 当前系统拓扑、项目状态与入口收敛口径以 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、`/AGENTS.md`、`/.omo/_truth/x4-consistency-rules.yaml` 为准。

---

## 第一章 · 架构分层

### §1.1 五层垂直主干

```
L4 自我层 · 数据面 · 被动
  └─ CARDS (SQLite) + Vault (Markdown)
  └─ 不运行代码, 不暴露 MCP
  └─ Agent 通过 L3 cockpit MCP 桥接访问

L3 入口层 · 工具面 · 主动
  └─ cockpit (CLI + MCP + Web)
  └─ 所有 Agent/用户统一入口
  └─ 唯一对外暴露 MCP 的生产者

I0 织层 · 路由面 · 中枢
  └─ agora (MCP Hub / BOS 路由)
  └─ 所有跨层通信的唯一通道
  └─ 端口与入口状态以 `protocols/port-registry.yaml` 与运行时探针为准

L2 内核三平面 · 引擎面
  ├─ 治理面: omo
  ├─ 引擎面: kairon
  ├─ 记忆面: gbrain
  └─ 编排: metaos

L1 运行时 · 基础设施
  └─ runtime (Matrix + Scheduler + KEI)

L0 协议编织 · 数据定义
  ├─ protocols/ (协议注册与端口 SSOT)
  └─ ecos (SSB + emergence)
```

### §1.2 三横切面

| 切面 | 核心 | 实现位置 |
|------|------|---------|
| **X1 审计** | KEI 沙箱 + 审计链 | runtime/kei_sandbox.py |
| **X2 抗熵** | 健康监控 + 自愈 | runtime/scheduler.py + autoheal.sh |
| **X3 价值栈** | LLM 成本 + 服务计量 | llm-gateway + omo/omo_cost.py |
| **X4 一致性** | CLI/端口/依赖/文档/CI/Phase 全量检查 | LAYER-INDEX.md + scripts/audit |

### §1.3 不变法则

1. **依赖方向**: L4 → L3 → I0 → L2 → L1 → L0 (只能自上而下)
2. **跨层调用**: 必须经 Agora I0 路由, 禁止直连 import
3. **L4 被动性**: L4 永远不运行代码, 永远不暴露 MCP
4. **L3 唯一入口**: 所有 Agent/用户通过 cockpit (L3) 接入
5. **协议先于实现**: 跨边界通信走 L0 注册 → I0 路由

---

## 第二章 · 接口标准

### §2.1 CLI 规范

| 规范 | 要求 |
|------|------|
| 命令名 | 项目名或域名 (如 `cockpit`, `agora`, `kos`) |
| 别名 | 仅保留一个, 废弃标注 SHIM 和截止日期 |
| 框架 | argparse (Python) / Click (Python) / bun CLI (TS) |
| 帮助 | 必须提供 `--help`, 必须包含示例 |
| JSON 输出 | 必须支持 `--json` 标志 (可机器消费) |

### §2.2 MCP 规范

| 规范 | 要求 |
|------|------|
| 工具名 | `{domain}_{action}` (如 `cards_status`, `research_list`) |
| 描述 | 中文描述, 含 Agent 调用时机 |
| 注册 | 经 Agora ProxyManager, 不独立暴露端口 |
| 版本 | 工具变更必须保持向后兼容 |
| 去重 | 同名工具以 Agora 前缀 `{service}.{tool}` 区分 |

### §2.3 HTTP 端口分配 (SSOT)

> 端口分配属于运行时事实，权威源是 `protocols/port-registry.yaml`。
> 本宪章只保留约束：所有端口必须先登记再使用，冲突裁决按层优先级执行。

### §2.4 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| 项目名 | 小写, 连字符 | `agora`, `cockpit`, `ecos` |
| Python 包 | `kairon_` 前缀 + 域名 | `kairon_utils`, `kairon_events` |
| Python 模块 | 小写, 下划线 | `dashboard_server.py` |
| MCP 工具 | `{domain}_{verb}` | `cards_status`, `research_create` |
| CLI 命令 | 小写, 无连字符 | `workspace context`, `agora health` |

---

## 第三章 · 代码标准

### §3.1 跨项目依赖

```
规则 1: import 只能从上到下 (L4→L3→I0→L2→L1→L0)
规则 2: 任何跨层调用必须经 Agora 路由
规则 3: kairon 不知道 agora 的存在 (agora 是 kairon 的 client)
规则 4: kairon 不知道 runtime 的存在 (runtime 是 kairon 的 infra)
规则 5: 跨语言边界 (Python↔TypeScript) 以 MCP 为唯一协议
```

### §3.2 Python 规范

| 规则 | 值 |
|------|-----|
| 版本 | >=3.10 (kairon), >=3.13 (omo/metaos) |
| 包管理 | uv (禁止 pip/poetry) |
| 格式化 | ruff format (双引号, 120 行宽) |
| Lint | ruff check (E,F,W,I,N,UP,S,PLE,RUF100) |
| 测试 | pytest + uv, fail_under 70% |
| 类型 | mypy namespace_packages |
| 导入 | isort via ruff |

### §3.3 TypeScript 规范 (gbrain)

| 规则 | 值 |
|------|-----|
| 运行时 | bun |
| 格式化 | bun fmt |
| 测试 | bun test |
| CI | bun run ci:local |

---

## 第四章 · 变更管理

### §4.1 OMO 治理循环

```
提出变更 → omo task create
  ↓
审议 → omo worker dispatch (分配 Agent)
  ↓
执行 → Agent 经 cockpit MCP → Agora → 项目执行
  ↓
验证 → 测试通过 + omo worker reclaim
  ↓
记录 → CARDS 写回 + .omo state 更新
```

### §4.2 债务管理

| 类型 | 定义 | 处理 |
|------|------|------|
| P0 | 立即修复 (生产缺陷) | 24h 内 |
| P1 | 本周修复 (架构偏差) | 7d 内 |
| P2 | 本月修复 (技术债务) | 30d 内 |
| P3 | 按需 (优化) | 排期 |

债务登记: `omo debt create` → `.omo/debt/items/`

### §4.3 代码冻结规则

```
触发条件: OMO code_freeze = true
冻结范围: 禁止非紧急 P0 修改
解冻条件: 人类手动解除或 Phase 完成
```

---

## 第五章 · CI/CD 要求

### §5.1 最低要求

| 项目 | 必须有 |
|------|--------|
| 所有 Python 项目 | pytest CI workflow |
| gbrain | bun test CI workflow |
| protocols (YAML) | meta-model-check CI |

### §5.2 当前覆盖

> 具体 CI 覆盖数量、workflow 数、通过率属于运行时事实。
> 以各项目仓库下的 `.github/workflows/` 与 workspace `governance-check` 为准。

---

## 第六章 · Agent 桥接协议

### §6.1 L4 → L3 → Agent 闭环

```
Agent 启动:
  ① workspace_context (cockpit MCP)
     → 知: 当前 Phase / P0 卡片 / 约束 / 下一步
  ② cards_check (cockpit MCP)
     → 审: 操作合规性
  ③ 执行: 经 Agora (I0) → L2/L1/L0
  ④ cards_update (cockpit MCP)
     → 归: 记录状态变更
```

### §6.2 MCP 配置 SSOT

```json
{
  "mcpServers": {
    "cockpit": {
      "command": "uv",
      "args": ["run", "--package", "cockpit", "cockpit-mcp"]
    }
  }
}
```

---

## 第七章 · 实施路线

> 本章只保留“宪章存在于一个演进语境中”的事实，不再维护当前阶段跟踪表。
> 当前路线、阶段、gate 与 closeout 证据以 `/.omo/goals/current.yaml`、`/.omo/state/system.yaml`、`/.omo/_delivery/` 为准。

---

## 第八章 · 不变项

以下在任何情况下不可变更：

1. **L4 不运行代码, 不暴露 MCP**
2. **L3 cockpit 是所有 Agent/用户的唯一入口**
3. **I0 Agora 是所有跨层通信的唯一通道**
4. **任何跨层调用必须经 Agora 路由, 禁止直连**
5. **修改后必须立即 git commit**

---

*宪章版本: v1.0 | 生效日期: 2026-06-06 | 下次审查: 2026-09-06*
*审批人: 夏明星 | SSOT 位置: `.omo/_truth/governance-charter-v1.md`*
