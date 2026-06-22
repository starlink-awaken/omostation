---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# 5+3+1 X 轴架构体系融合设计 (X-Axis Architecture Consolidation)

> 2026-06-06 · X1-X4 全面系统化 · 所有保障机制一次性固化

---

## 一、X 轴总览 (最终版)

```
         X1 审计     X2 保鲜     X3 价值     X4 一致性
         (安全)     (新鲜)     (成本)     (规则遵守)
           │          │          │          │
L4 自我层 ─┤          │     ●    │     ●    │ 端口注册
L3 入口层 ─┤          │          │     ●    │ cards_check
I0 织层   ─┤     ●    │     ●    │     ●    │ 端口冲突检测
L2 内核   ─●──────────●──────────●──────────┤ INTERFACE.yaml
L1 运行时 ─●──────────●──────────┤     ●    │ CI 验证
L0 协议   ─┤          │          │     ●    │ port-registry.yaml
```

## 二、机制-体系映射

每个保障机制 = 具体的横向切面实现:

### X1 审计链 (已实现)

| 机制 | 实现位置 | 状态 |
|------|---------|------|
| KEI 沙箱 | `runtime/kei_sandbox.py` | ✅ 文件/网络/子进程拦截 |
| KEI 审计日志 | `runtime/data/kei_audit.jsonl` | ✅ JSONL 审计 |
| Agora Auth 中间件 | `agora/server/mcp.py` | ✅ MCP 认证 |
| 端口安全验证 | `agora/core/registry.py:register()` | ✅ 冲突阻断 |

### X2 保鲜链 (已实现)

| 机制 | 实现位置 | 状态 |
|------|---------|------|
| Matrix Scheduler | `runtime/scheduler.py` | ✅ 15s 心跳 + autoheal |
| 文档保鲜检查 | `scripts/check-interfaces.py --doc-only` | ✅ CI cron 每周一 |
| OMO 债务保鲜 | `omo_debt.py` (state/freshness) | ✅ 周期检查 |
| CARDS 保鲜 | `cockpit/cards_status.py` (stale detection) | ✅ 72h 阈值 |

### X3 价值链 (已实现)

| 机制 | 实现位置 | 状态 |
|------|---------|------|
| LLM 成本追踪 | `omo_cost.py` → `llm_cost.jsonl` | ✅ 10 模型定价 |
| LLM Gateway | `llm-gateway-kernel` | ✅ 路由 + 配额 |
| CARDS 价值优先级 | P0/P1/P2/P3 分级 | ✅ 治理 |

### X4 一致性 (新增, 已实现)

| 机制 | 实现位置 | 状态 |
|------|---------|------|
| CLI 入口验证 | `scripts/check-interfaces.py` | ✅ CI push |
| 端口冲突检测 | `check-interfaces.py` + `agora/registry.py` | ✅ CI + runtime |
| 跨层 import 检查 | `scripts/check-cross-deps.py` | ✅ CI push |
| 文档保鲜 | `scripts/check-interfaces.py --doc-only` | ✅ CI cron |
| CI 覆盖率 | `.github/workflows/` 扫描 | ✅ 9/9 |
| Agent 启动链 | `CLAUDE.md §0` + `workspace_context` | ✅ 每次对话 |
| Phase 门禁 | `omo goals current.yaml` + X4 check | ✅ 条件验证 |
| 接口注册表 | `INTERFACE.yaml` × 7 项目 | ✅ 声明式 |

## 三、L0 协议-机制绑定

所有保障机制对应的 L0 协议定义:

| 协议 | 机制 |
|------|------|
| `ports.yaml` (port-registry) | X4 端口冲突检测 |
| `interface-registry.yaml` (待创建) | X4 CLI/MCP 一致性 |
| `x4-governance-compliance.yaml` (待创建) | X4 规则合规度量 |
| `L0-registry.yaml` (已有) | 16 协议元注册 |

## 四、巩固保障 (不遗忘)

### 4.1 文档层
- CLAUDE.md §0 → 列出所有 X4 约束
- governance-charter-v1.md → §1.3 端口, §7.4 X4
- INTERFACE.yaml × 7 → 每项目声明能力

### 4.2 代码层
- CI: 3 scripts × 2 workflows
- Runtime: Agora register() + cockpit cards_check()
- Memory: CodeBuddy 自动加载

### 4.3 自动化层
```
CI push → check-interfaces + check-cross-deps
CI cron (周一 8:00) → doc-freshness + port-freshness
Agora register → port conflict → ValueError
cockpit cards_check → 操作前合规验证
```

## 五、X 轴融合完成度

| 维度 | 规则数 | 实现率 | 自动化 |
|------|--------|--------|--------|
| X1 审计 | 5 | 100% | 沙箱自动拦截 |
| X2 保鲜 | 4 | 100% | scheduler 自动 + CI cron |
| X3 价值 | 3 | 80% | LLM cost 记录 |
| X4 一致性 | 8 | 100% | CI + runtime 双重 |

**X 轴 = 保障机制的总称。每增加一个保障机制, 只需回答: "它属于 X1/X2/X3/X4 哪个维度?" 然后按对应协议注册、CI 加入、文档更新。**
