# X 轴实现注册表 (Implementation Registry)

> ⚠️ **已降级为人类可读视图(2026-06-08)**。机器可读 SSOT 迁移至 `protocols/x-axis-registry.yaml`,
> 含 probe 探活声明 + known_state 实测。本文不再手工维护实现状态 —— 以 YAML + `omo x-axis check` 实测为准。
> **迁移原因**:本文曾声称 X1/X2/X3 已实现,但 probe 实测发现声明/现实分裂
> (如 X1/K2 审计日志 system.yaml 报 EMPTY、实测 14.9 万条活跃)。详见 `x-plane-architecture-design-v1.md` §1。
>
> 可变 · 实现级 · 不纳入架构定义
> 对应架构: LAYER-INDEX.md §X1-X4 (原则定义)

---

## X1 审计链 (操作安全)

| ID | 机制 | 实现位置 | 阻断方式 |
|----|------|---------|---------|
| X1/K1 | KEI 安全沙箱 | `runtime/kei_sandbox.py` | `sys.addaudithook` 运行时拦截 |
| X1/K2 | KEI 审计记录 | `runtime/data/kei_audit.jsonl` | JSONL 持久化 |
| X1/K3 | Agora MCP 认证 | `agora/server/mcp.py` | API Key / JWT 中间件 |
| X1/K4 | 端口安全验证 | `agora/core/registry.py:register()` | `ValueError` 阻断冲突 |
| X1/K5 | OMO 约束检查 | `cockpit/cards_check` MCP | `violations != []` |

## X2 保鲜 (数据新鲜)

| ID | 机制 | 实现位置 | 阻断方式 |
|----|------|---------|---------|
| X2/K1 | 服务健康监控 | `runtime/scheduler.py` + `autoheal.sh` | 15s 心跳 + 指数退避自愈 |
| X2/K2 | 文档保鲜检查 | `scripts/check-interfaces.py --doc-only` | CI cron 每周一，>90d RED |
| X2/K3 | 债务保鲜 | `omo/omo_debt.py` (freshness state) | 7d review 周期 |
| X2/K4 | CARDS 过期检测 | `cockpit/cards_status` MCP | 72h stale 标记 |
| X2/K5 | CI 工作流保鲜 | `.github/workflows/governance-check.yml` | cron + push |

## X3 价值栈 (投入产出)

| ID | 机制 | 实现位置 | 阻断方式 |
|----|------|---------|---------|
| X3/K1 | LLM 成本追踪 | `omo/omo_cost.py` → `llm_cost.jsonl` | 10 模型定价表 |
| X3/K2 | LLM Gateway 路由 | `llm-gateway-kernel` | 排队 + 限流 |
| X3/K3 | CARDS 优先级分级 | P0/P1/P2/P3 frontmatter | 治理驱动 |

## X4 一致性 (规则遵守)

| ID | 机制 | 实现位置 | 阻断方式 |
|----|------|---------|---------|
| X4/K1 | CLI 入口注册验证 | `scripts/check-interfaces.py` | CI push → 未注册 RED |
| X4/K2 | 端口冲突检测 | `check-interfaces.py` + `agora/registry.py` | CI + runtime 双重阻断 |
| X4/K3 | 跨层 import 检查 | `scripts/check-cross-deps.py` | CI push → 违规 RED |
| X4/K4 | 接口注册表 | `INTERFACE.yaml`（按项目分布） | 声明式 + CI 一致性验证 |
| X4/K5 | 端口注册表 | `protocols/port-registry.yaml` | 先注册后使用, CI 检查 |
| X4/K6 | Agent 启动契约 | `CLAUDE.md §0` + `workspace_context` | Agent 对话即读 |
| X4/K7 | Phase 门禁 | `.omo/_truth/goals/current.yaml` + X4 score | score ≥ 90 |
| X4/K8 | 跨项目依赖检查 | `scripts/check-cross-deps.py` | CI push RED |

## 维护规则

```
新增机制 → 注册到本文档 (X/K-ID)
修改实现 → 更新本文档的位置/阻断列
移除机制 → 删除本文档对应行 + 标注归档时间

本文档是架构 LAYER-INDEX.md X 轴部分的实现映射。
LAYER-INDEX.md 说"是什么"，本文档说"怎么实现的"。
```

---

*最后更新: 2026-06-06 · 20 项实现注册*
