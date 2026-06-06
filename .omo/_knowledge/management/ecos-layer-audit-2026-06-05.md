> [!WARNING]
> **DEPRECATED**: 本文档描述的 4+1+3 架构或旧版 eCOS 映射已过时。请参考最新的 **eCOS v5.0 (5+3+1)** 宪法大纲：`~/Documents/学习进化/2-knowledge/基建架构/phase6-完成化/pat-45-eCOS-v5-architecture.md`。


# eCOS Layer Audit — 2026-06-05

> 审计时间：2026-06-05 21:00 CST
> 审计范围：L0/L1/I0/X1-X3 运行时状态
> 审计方法：端口探测 + 进程检查 + 代码审查

## 审计结果

### I0 — Agora 集成织物

| 检查项 | 结果 | 结论 |
|--------|------|------|
| Docker Agora PID | integration-agora-1 (Up 4h) | ✅ 运行 |
| Native Agora PID | 10552 (uv run), 10553 (python3) | ❌ 多余实例 |
| Agora SSE :7431 | HTTP 000 | ❌ 不可达 |
| Docker Agora SSE :7432 | HTTP 000 | ❌ 不可达 |
| Docker Agora MCP :7435 | HTTP 404 | ❌ 路径错误 |
| 健康 API :7426 | HTTP 000 | ❌ 不可达 |

**结论：** 双 Agora 实例冲突，Docker 端口映射错位(7422→7426, 7430→7435, 7431→7432)，所有 SSE/MCP/健康端点均不可达。

### L0 — 协议注册表

| 检查项 | 结果 | 结论 |
|--------|------|------|
| 注册协议数 | 16 | ✅ 文档完整 |
| 有运行时的协议 | MCP 仅 1 个 | ❌ 15/16 无运行时 |
| ACP | 无实现 | ❌ 文档存根 |
| A2A | planned | ❌ 文档存根 |
| TaskObject | 规范 `.md` | ❌ 零消费 |

**结论：** 协议覆盖率高但运行时覆盖率极低。

### L1 — 运行时矩阵

| 检查项 | 结果 | 结论 |
|--------|------|------|
| 服务注册数 | 11 | ✅ 文档完整 |
| Matrix Scheduler 进程 | 无 | ❌ 未运行 |
| matrix_state.json | 有数据 (timestamp 1780635221) | ⚠️ 单点无历史 |
| health-scan 脚本 | 存在 | ✅ |
| 定时刷新 | 无 cron job | ❌ |

**结论：** CLI 工具齐全但缺少持续运行的后台调度器。

### X1 — 治理安全

| 检查项 | 结果 | 结论 |
|--------|------|------|
| KEI sandbox 代码 | 存在 (kei_sandbox.py) | ✅ |
| audit hook 激活 | `sys.addaudithook()` 从未调用 | ❌ |
| kei.yaml 规则加载 | 无进程读取 | ❌ |
| 操作审计链 | 无 | ❌ |

### X2 — 抗熵

| 检查项 | 结果 | 结论 |
|--------|------|------|
| 保鲜追踪 | 无 | ❌ |
| 健康历史 | 无 | ❌ |
| 自动恢复 | 无 | ❌ |

### X3 — 价值堆栈

| 检查项 | 结果 | 结论 |
|--------|------|------|
| runtime_stats 工具 | 存在 | ✅ |
| _STATS 计数器 | 定义但 `+=1` 从未执行 | ❌ |
| MCP 调用统计 | 无 | ❌ |

## 债务总结

| 优先级 | ID | Severity | Weight | 层 |
|--------|----|----------|--------|----|
| P0 | I0-AGORA_SSE_DEAD | high | 0.8 | I0 |
| P1 | I0-AGORA_DUAL_INSTANCE | medium | 0.6 | I0 |
| P1 | X1-SANDBOX_INERT | medium | 0.6 | X1 |
| P2 | L0-PROTOCOL_GHOSTS | medium | 0.5 | L0 |
| P2 | L1-SCHEDULER_MISSING | medium | 0.5 | L1 |
| P3 | L1-HEALTH_STALE | low | 0.3 | L1 |
| P3 | X2-NO_FRESHNESS | low | 0.3 | X2 |
| P4 | X1-NO_AUDIT_CHAIN | low | 0.2 | X1 |
| P4 | X3-NO_COSTING | low | 0.2 | X3 |
| P4 | L0-TASKOBJECT_UNUSED | low | 0.2 | L0 |

## 修复建议

按优先级顺序：
1. **I0 整治** — 杀掉 native Agora，统一 Docker 端口映射，恢复 SSE 可达
2. **X1 治理激活** — 加 health-scan cron job 启用 KEI sandbox audit hook
3. **L1 调度器** — 建定时 health-scan cron job
4. **X2/X3 渐进** — 加 freshness 追踪和 tool call 计数器
