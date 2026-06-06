# 5+3+1 全局治理宪章 (Architecture Governance Charter)

> **宪法级文档** · 2026-06-06 颁布 · 覆盖 9 项目 · 不允变更核心原则
> **审查周期**: 每次会话启动检查 §0 · 每月全面审查
> **生效范围**: 所有 9 个项目 · 所有 Agent · 所有人类开发者

---

## §0 架构宪法

### 0.1 5+3+1 分层 (不可变)

```
L4 自我层   — 纯文档 · 被动 (CARDS SQLite + Vault Markdown)
L3 入口层   — Cockpit (CLI + MCP + Web) · 统一 Agent 桥接
I0 织层    — Agora (MCP Hub · 服务发现/路由/代理) · 所有跨层通信唯一通道
L2 内核    — OMO(治理) + Kairon(25包引擎) + gbrain(163K TS 记忆) + MetaOS(编排)
L1 运行时   — Runtime (Matrix 注册表 + 健康监控 + KEI 沙箱 + Scheduler)
L0 协议    — Protocols(16 YAML) + eCOS(SSB 签名链 + 涌现计算)

X1 审计链 · X2 抗熵进化 · X3 价值堆栈 · X4 治理一致性 ← 横向贯穿所有层

**保障体系**: 
  架构原则: `LAYER-INDEX.md` §X1-X4 (定义"是什么", 稳定)
  实现注册: `.omo/_knowledge/management/x-axis-implementation-registry.md` (定义"怎么实现", 可变)
```

### 0.2 不可变原则 (10 条)

1. **L4 不跑代码**: 不部署 MCP server, 不成为运行时
2. **Agent 走 L3**: Agent 通过 cockpit MCP `workspace_context` 获取上下文, 禁止直接读 L4 文件
3. **跨层走 I0**: 任何跨层调用必须经 Agora 路由, 禁止直接 import 跨项目包
4. **L1 管 L1**: Runtime 是唯一服务注册/健康检查/自动愈合的权威
5. **SSOT 唯一**: 每个事实只有一个权威位置, 指针优于副本
6. **CARDS 优先**: 任务/债务/想法走 CARDS (Markdown frontmatter), 不散落
7. **协议先于实现**: 跨边界通信走 L0 协议注册 → I0 路由
8. **修改后立即 git commit**: 任何代码/配置修改后立即提交
9. **禁止直接改写 .omo 目录**: 通过 OMO CLI 或 cockpit MCP 工具操作
10. **测试门禁**: 修改包后必须运行对应测试, 通过率 ≥ 95%

---

## §1 接口标准 (Interface Standards)

### 1.1 CLI 规范

```
入口点命名: {项目}-{功能}
  如: cockpit-mcp, ecos-ssb, omo-debt
  别名允许: workspace → cockpit (兼容旧名)

子命令组织:
  按领域分组: context/cards/vault/research/status/code/governance
  所有 CLI 使用 argparse 或 Click

必须提供的子命令:
  {cli} version    — 版本信息
  {cli} help       — 帮助 (默认面板)
```

### 1.2 MCP 规范

```
MCP Server 注册: 所有 MCP server 通过 Agora ProxyManager 注册
  格式: uv run --package {pkg} python -m {pkg}.mcp_server

工具命名:
  {service}_{tool} — 内部 (Agora proxy 路由)
  {tool_name}      — 直接暴露 (cockpit/agora 公共入口)

工具描述规范:
  ★ 标记 Agent 应首先调用的工具
  Agent 引导词: "应先调用", "应在执行前调用", "用于获取上下文"

MCP 配置 SSOT:
  参见 cockpit README: 标准 JSON 配置模板
```

### 1.3 HTTP 规范

```
端口分配 (SSOT):
  7422 — Agora MCP HTTP        (FastMCP, I0)
  7430 — Agora Dashboard       (FastAPI, I0)
  7431 — Agora MCP SSE         (FastMCP, I0)
  8090 — Cockpit Web Dashboard (http.server, L3)
  9090 — eCOS Dashboard        (http.server, L0)
  动态  — Runtime Cron         (FastAPI, L1)

端口注册 (SSOT: protocols/port-registry.yaml):
  所有端口必须先在 port-registry.yaml 注册，后在代码中使用
  新端口注册流程:
    1. 检查 port-registry.yaml → 确认未被占用
    2. 添加端口条目 (格式: PORT: service-name # project · protocol · desc)
    3. CI push 时自动验证 (check-interfaces.py)
    4. 代码中使用环境变量: {SERVICE}_PORT
  冲突裁决: I0 > L3 > L2 > L1 > L0 (优先级递减)
  阻断机制: CI + Agora register() 双重检测
```

### 1.4 命名规范

```
Python 包:  kebab-case (kairon-utils, kairon-lib-events)
Python 模块: snake_case (kairon_utils, kairon_events)
TypeScript: camelCase (gbrain, hermesConsole)
CLI 入口:    kebab-case (cockpit-mcp, ecos-ssb)
MCP 工具:    snake_case (workspace_context, cards_status)
```

---

## §2 依赖治理 (Dependency Rules)

### 2.1 分层依赖矩阵

```
层    可依赖                   不可依赖
──────────────────────────────────────────────
L4    —                        L3/L2/L1/L0 (不跑代码)
L3    L4 (只读文档)            L2/L1/L0 (只通过 Agora)
I0    L3 (可选)                L2 (仅通过 kairon 可选依赖)
L2    同层 (L2↔L2 允许)       L1/L0 (通过 I0)
L1    L0 (协议 YAML)           L2 (通过 Agora)
L0    —                        所有上层
```

### 2.2 跨项目 Import 规则

```
✅ 允许:
  - kairon 包间内部 import (同 monorepo)
  - cockpit → runtime (L3 强依赖 L1)
  - 任何 → kairon-lib-events / kairon-utils (L0 基础包零依赖)

❌ 禁止:
  - cockpit → kairon.agora (应通过 Agora MCP, 非 import)
  - kairon → cockpit (向上依赖)
  - ecos → kairon (应由 kairon 调 ecos, 非反向)
  - 跨项目直连 import (不走 Agora)
```

### 2.3 已拉平的基础依赖

| 包 | 被依赖数 | 零运行时依赖 |
|----|---------|------------|
| kairon-lib-events | 5 | ✅ stdlib only |
| kairon-utils | 12 | ✅ stdlib only |
| kairon-plugin-sdk | 3 | ✅ stdlib only |
| kairon-observability | 2 | ✅ stdlib only |
| kairon-pipeline | 2 | ✅ stdlib only |
| core-models | 8 | ✅ |

---

## §3 债务分类 (Debt Classification)

### 3.1 X1/X2/X3 三维标定

```
每个 OMO debt 必须标注:
  x1_policy_ref:    安全/合规/审计 相关约束 (如 BYPASS-xxx)
  x2_freshness:     保鲜/过期 状态 (fresh/stale/dormant)
  x3_tier:          价值层级 (P0/P1/P2/P3)

X1 审计维度:
  BYPASS:   跨层直连违反 §0.2 原则
  HARDCODE: 硬编码路径 (违反 §0.2 SSOT)
  AUTH:     认证/鉴权 缺失
  SANDBOX:  KEI 沙箱未覆盖

X2 保鲜维度:
  fresh(<7d) → stale(7-30d) → dormant(>30d)
  债务 owner 必须 7 天内 review

X3 价值维度:
  P0: 安全/可用性 阻塞 → 立即修复
  P1: 架构偏差/技术债 → 本 Phase 内修复
  P2: 优化/改进 → 下 Phase 排期
  P3: 可延后 → backlog
```

### 3.2 债务登记流程

```
1. 发现问题 → OMO CLI: omo debt register
2. 标注 X1/X2/X3 → 三维分类
3. 关联 CARDS → cards link {card_id}
4. 记录证据 → evidence_refs
5. 修复后 → omo debt close --evidence
```

---

## §4 测试标准 (Testing Standards)

### 4.1 单包测试

```
覆盖率门禁:
  L0 基础包: ≥ 80% (events/utils/plugin-sdk/...)
  L1 Runtime: ≥ 70% (critical path)
  L2 Kairon:  ≥ 60% (per-package)
  I0 Agora:  ≥ 80% (critical path)
  L3 Cockpit: ≥ 70%

命名规范:
  test_{module}.py — 单元测试
  test_{feature}_*.py — 功能测试

快速验证:
  make test-diff — 仅测试修改的包
  make test-fast — 跳过 integration/benchmarks
```

### 4.2 全量测试

```
make test — 遍历所有的 packages/*/tests/
CI gate: fail_under 70% (coverage)

已知豁免:
  kos (300 tests, 需运行中服务)
  minerva (需 Ollama + SearXNG)
  ontoderive (需 LLM backend)
```

---

## §5 文档标准 (Documentation Standards)

### 5.1 SSOT 文件 (每个项目必须有)

| 文件 | 内容 | 受众 |
|------|------|------|
| `CLAUDE.md` | §0 启动指令 + 架构定位 + 本域专有规则 | Claude Code Agent |
| `AGENTS.md` | 开发者指南 (命令/测试/CI/Gotchas) | 其他 Agent + 人类开发者 |
| `README.md` | 简介 + 接口列表 + MCP 配置 + 测试命令 | 外部用户 |

### 5.2 默认面板 (CLI 标准)

```
{cli} (无参数) → 显示默认面板:
  ┌─ 上下文 ─── 当前状态摘要 ──────────┐
  ├─ 快速入口 ── 常用命令 3-5 条 ──────┤
  ├─ 工具 ───── 功能分组 ──────────────┤
  └─ 帮助 ───── {cli} help ─────────────┘
```

### 5.3 更新纪律

```
每次重大变更后必须更新:
  §0 强制指令 (CLAUDE.md)
  接口统计 (README.md)
  测试命令 (AGENTS.md)

审查周期:
  CLAUDE.md 每月审查 → 保鲜检查自动提醒
  README 每次接口变更后更新
```

---

## §6 CI/CD 标准

### 6.1 Workflow 规范

```
命名: {project}-ci.yml
触发: [push, pull_request]
步骤:
  1. checkout
  2. setup-python/bun
  3. uv sync / bun install
  4. pytest / bun test

必须排除:
  tests/e2e (网络依赖)
  tests/integration (服务依赖)
  tests/benchmarks (性能依赖)
```

### 6.2 当前状态

```
9/9 项目 CI 覆盖 (2026-06-06 补齐)
  kairon: 7 workflows ✅
  omo:    3 workflows ✅
  agora:  1 workflow (agora-ci) ✅
  cockpit: 1 workflow (cockpit-ci) ✅
  metaos: 1 workflow (metaos-ci) ✅
  ecos:   1 workflow (ecos-ci) ✅
  gbrain: 1 workflow (gbrain-ci) ✅
  runtime: 1 workflow (meta-model-check) ✅
  protocols: 0 (纯数据层, via meta-model) ✅
```

---

## §7 治理流程 (Governance Process)

### 7.1 Agent 启动链

```
MANDATORY §0 (每次会话第一步):
  1. 连接 cockpit MCP → 调 workspace_context
  2. 调 cards_check → 验证约束合规
  3. 获取 P0 卡片 → 优先处理
  4. 执行 → 调 cards_update 写回状态

禁止:
  ❌ 跳过上下文直接修改代码
  ❌ 绕过 Agora 直接调 L2
  ❌ 跳过 CARDS 散落管理任务
```

### 7.2 周常治理

```
每 7 天执行:
  workspace health — 全系统健康检查
  审查 CLAUDE.md 保鲜
  更新 debt registry (X2 新鲜度)
  检查 CI workflow 运行状态
```

### 7.3 Phase 迁移

```
Phase 目标: .omo/_truth/goals/current.yaml
迁移流程:
  1. 所有 P0 debt 关闭
  2. 所有 CI 通过
  3. 文档保鲜检查 (<30d)
  4. X4 Score ≥ 90 且 0 critical violations
  5. 更新 phase 状态 → done
```

### 7.4 X4 治理一致性检查

参见 `.omo/_knowledge/management/x4-governance-consistency-design.md`。每次 Phase 迁移必须通过 X4 检查。

```
每周一早8: CI cron → X4 check → 报告
  score < 80 → omo debt P0
  critical > 0 → 阻断 Phase 迁移
```

---

## §8 附录

### 8.1 快速参考卡

```
MCP 启动:  uv run --package cockpit cockpit-mcp
Web 面板:  uv run --package cockpit cockpit-dashboard
健康检查:  workspace health
CARDS:     workspace cards
上下文:    workspace context
全量测试:  make test
差异测试:  make test-diff
OMO 债务:  omo debt list
```

### 8.2 例外与豁免

```
免于 §0.2-1 (L4 不跑代码):
  驾驶舱健康检查脚本 (CLI 工具, 非运行时)

免于 §0.2-3 (跨层走 I0):
  cockpit → runtime (L3 强依赖 L1, 已声明)
  kairon 内部包间 import (同 monorepo, 非跨层)

免于 §4.1 (测试门禁):
  见 §4.2 已知豁免列表
```

### 8.3 宪章修订流程

```
1. 通过 OMO debt 提交修订提案 (标注 charter-amendment)
2. CARDS link 关联受影响模块
3. 影响分析: 列出所有违反旧规则的现有代码
4. 经 X1/X2/X3 三维审查
5. 更新本文档 + 同步所有受影响的 CLAUDE.md/AGENTS.md
```

---

*颁布: 2026-06-06 · 首次全面审查: 2026-07-06 · 不允核心原则变更*
