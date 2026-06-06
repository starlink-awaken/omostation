# 5+3+1 治理体系总览 (Governance Master Index)

> 2026-06-06 · 全量整理 · 所有治理策略和机制的 SSOT

---

## 一、治理文档索引 (14 文件)

### 宪法级 (不可变)
| 文档 | 位置 | 说明 |
|------|------|------|
| 全局治理宪章 v1 | `.omo/_knowledge/management/governance-charter-v1.md` | 10 条不可变原则 + 8 章 |
| L4-L3-Agent 桥接协议 | `.omo/_knowledge/management/l4-l3-agent-bridge-canon.md` | L4 被动 / L3 桥接 / Agent 执行器 |
| 5+3+1 分层索引 | `LAYER-INDEX.md` | 9 项目 + 5 层 + CI 状态 |

### 策略级 (可变, 需审查)
| 文档 | 位置 | 说明 |
|------|------|------|
| 强制执行机制 | `.omo/_knowledge/management/governance-enforcement-v1.md` | 5 层防御体系设计 |
| 接口架构治理 | `.omo/_knowledge/management/interface-governance-2026-06-06.md` | CLI 21 / MCP 286 / HTTP 9 统计 |
| 统一接口层设计 | `.omo/_knowledge/management/unified-interface-design-v1.md` | Interface Registry 设计方案 |
| 全量审计报告 | `.omo/_knowledge/management/5+3+1-full-audit-2026-06-06.md` | 9 项目全量审计 + 21 债务 |
| 架构全局方案 | `.omo/_knowledge/management/architecture-complete-plan.md` | 0→9 项目迁移路线图 |

### 操作级
| 文档 | 位置 | 说明 |
|------|------|------|
| OMO Goals (current) | `.omo/_truth/goals/current.yaml` | 当前 Phase + 目标状态 |
| Kairon 问题台账 | `projects/kairon/docs/kairon-issue-ledger.md` | 21→0 债务追踪 |
| Kairon CLAUDE.md | `projects/kairon/CLAUDE.md` | 25 包 monorepo 指南 |
| Kairon AGENTS.md | `projects/kairon/AGENTS.md` | CI/测试/依赖规范 |
| 驾驶舱 CLAUDE.md | `~/Documents/CLAUDE.md` | L4 自我层网关 v5.1 |
| 驾驶舱 AGENTS.md | `~/Documents/AGENTS.md` | 非 Claude Agent 指针 |
| Vault CLAUDE.md | `~/Documents/学习进化/CLAUDE.md` | L4 数据面定位 |

---

## 二、执行机制清单 (7 项)

### 2.1 CI 自动检查

| 脚本/Workflow | 检查内容 | 频率 |
|--------------|---------|------|
| `scripts/check-interfaces.py` | CLI 一致性 + 端口冲突 + 文档保鲜 | CI push |
| `scripts/check-cross-deps.py` | 跨层 import 违规 | CI push |
| `.github/workflows/governance-check.yml` | 上述两项 + 每周 cron | push + 周一 8:00 |

### 2.2 Runtime 工具

| MCP 工具 | 位置 | 功能 |
|---------|------|------|
| `workspace_context` | cockpit MCP | Agent 启动上下文 (Phase/P0/约束/引导) |
| `cards_status` | cockpit MCP | CARDS 活跃卡片列表 |
| `cards_check` | cockpit MCP | 操作前约束合规验证 |
| `vault_search` | cockpit MCP | L4 Vault 知识检索 |

### 2.3 周常脚本

| 脚本 | 位置 | 功能 |
|------|------|------|
| `ecos-health-check.py` | `~/Documents/驾驶舱/scripts/` | 全系统健康检查 |
| `ecos-daemon.py` | `~/Documents/驾驶舱/scripts/` | 守护进程 |
| `ecos-brief.py` | `~/Documents/驾驶舱/scripts/` | 会话简报 |
| `check-claude-freshness.py` | `~/Documents/驾驶舱/scripts/` | 文档保鲜 |

---

## 三、治理原则清单 (10+12 条)

### 3.1 宪法原则 (10 条, 不可变)

1. L4 不跑代码
2. Agent 走 L3
3. 跨层走 I0
4. L1 管 L1
5. SSOT 唯一
6. CARDS 优先
7. 协议先于实现
8. 修改后立即 git commit
9. 禁止直接改写 .omo
10. 测试门禁 ≥95%

### 3.2 接口原则 (12 条)

1. CLI 入口: kebab-case (`cockpit-mcp`)
2. MCP 工具: snake_case (`workspace_context`)
3. MCP 入口统一: 通过 Agora ProxyManager
4. 端口: 环境变量 `{PROJECT}_PORT`
5. 端口冲突: I0 > L3 > L2 > L1 > L0
6. 文档: 每个项目 CLAUDE.md + AGENTS.md + README.md
7. CLI 默认面板: 无参数 → 上下文 + 快速入口 + 工具 + 帮助
8. MCP 工具描述: ★ 标记 Agent 首先调用 + 调用时机
9. 命名空间: Python kebab-case → module snake_case
10. 版本格式: 独立项目 SemVer, kairon 包独立版本
11. 跨项目通信: 仅通过 Agora, 不直接 import
12. 新接口: 先在 INTERFACE.yaml 注册, 后实现

---

## 四、当前状态汇总 (2026-06-06)

### 4.1 项目架构

```
9 项目 · 5+3+1 分层
├── L4 自我层: CARDS (SQLite) + Vault (Markdown)
├── L3 入口层: cockpit (CLI 18 + MCP 20 + Web 8 API, 498 tests)
├── I0 织层:  agora (CLI 35 + MCP 42 + HTTP 4 ports, 1105 tests)
├── L2 内核:  kairon (25 packages, 1810+ tests)
│             omo (CLI 28 + MCP 10, 221 tests)
│             gbrain (MCP 67, TS 163K)
│             metaos (MCP 11, 163 tests)
├── L1 运行时: runtime (CLI 3 + MCP 30 + HTTP, 171 tests)
└── L0 协议:  ecos (CLI 3 + HTTP :9090, 122 tests)
              protocols (16 YAML)
```

### 4.2 CI 覆盖

```
18 workflows, 9/9 项目覆盖 (100%)
  kairon: 7  omo: 3  runtime: 1
  agora: 1  cockpit: 1  metaos: 1  ecos: 1  gbrain: 1
  governance: 1 (新增)  sharedbrain: 1
```

### 4.3 债务状态

```
21 项已修复 (0 严重)
剩余低优: 端口冲突 8765/9090 (遗留), SHIMs (待清理)
```

### 4.4 MCP 工具分布

| 项目 | 工具数 |
|------|--------|
| agora | 66 (41 FastMCP + 25 Registry) |
| gbrain | 75 (TS) |
| kairon packages | 92 |
| cockpit | 20 |
| omo | 12 |
| metaos | 11 |
| runtime | 9 |
| **总计** | **285** |

---

## 五、治理流程 (3+1)

### 5.1 Agent 启动流程

```
① 连接 cockpit MCP
② 调 workspace_context → 获取 Phase/P0/约束/引导
③ 调 cards_check → 验证操作合规
④ 执行 (经 Agora → L2)
⑤ 调 cards_update → 写回状态
```

### 5.2 新增项目流程

```
1. LAYER-INDEX.md 注册 (层归属 + 职责)
2. INTERFACE.yaml 声明能力 (CLI/MCP/HTTP)
3. pyproject.toml (hatchling + uv workspace)
4. CI workflow (.github/workflows/{project}-ci.yml)
5. README.md (含 MCP 配置 SSOT)
6. OMO 登记 (初始债务为空)
```

### 5.3 归档项目流程

```
1. 验证 0 外部 import
2. 移至 projects/_archived/
3. 更新 LAYER-INDEX.md (⚪)
4. 更新 uv.sources (移除)
5. OMO 登记
```

### 5.4 日常运维

```
每日: Agent workspace_context 获取上下文
每周: P0 债务清理 + CI 检查 + 文档保鲜
每月: OMO goals 审查 + 架构对齐审计
每季: 全量测试 + 依赖升级 + 宪章修订
```

---

## 六、长保记忆 (不会遗忘)

### 6.1 内存级 (每次会话自动加载)

| 记忆文件 | 内容 |
|---------|------|
| `shared_lib_extraction_20260606.md` | 5 子包拆解记录 |
| `architecture_5p3p1_analysis_20260606.md` | 9 项目验证 |
| `l4-l3-agent-bridge-canon.md` | 桥接协议 |
| `governance-charter-v1.md` | 宪章引用 |

### 6.2 文档级 (每次 Agent 启动必读)

```
Workspace/CLAUDE.md §0 → 指向: governance-charter + workspace_context
kairon/CLAUDE.md → 交叉引用 Workspace CLAUDE.md
~/Documents/CLAUDE.md → L4 网关, 指向 cockpit MCP
```

### 6.3 OMO 级 (持久化, 可查询)

```
.goals/current.yaml → Phase + 目标状态
.debt/items/ → 债务登记
.plan/ → 执行计划
```

### 6.4 运行时级 (自动触发)

```
CI push → check-interfaces/check-cross-deps
CI cron → 每周一文档保鲜
ecos-health-check → 一键健康扫描
cards_check → Agent 操作前验证
```

---

*整理完成: 2026-06-06 · 14 文档 + 7 机制 + 22 原则 + 4 流程*
