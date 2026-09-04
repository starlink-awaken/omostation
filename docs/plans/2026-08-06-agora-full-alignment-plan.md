---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# agora 全面规划与方案设计 (2026-08-06)

> 架构/战略/场景/功能对齐 + 文档配置规则依赖同步。
> 目标: 从"MCP 网关"对齐到"能力编排大脑", 消除声明/实现/文档三重漂移。

## 一、架构与战略对齐

### 1.1 定位确认
- agora = **I0 织层** (docs/project-registry.yaml:45-53, role="MCP Hub · BOS URI 路由")
- 演进方向: 网关 → 能力编排大脑 (ARCHITECTURE.md:99 已承担 discovery+capability routing)
- **战略目标**: AI agent 经 `bos://` 跨层调用的统一入口 + 能力生命周期治理 (B1度量→B2路由→B3发现)

### 1.2 已具备能力 (P1+P2 深化后)
| 能力 | 状态 | 证据 |
|---|---|---|
| 路由 (Trie+语义) | ✅ | bos_router.py:406 resolve_with_capability |
| 编排 (a2a) | ✅ | a2a_send_task |
| 准入 (admission SPI) | ✅ | admission/port.py (metaos 软绑定) |
| 审计 (hashchain) | ✅ | mcp.py verify_chain → /health audit_chain |
| 可观测 (health/metrics) | ✅ | mcp_entry /health + /metrics |
| 治理 (9 tools) | ✅ | tools_governance |
| 能力生命周期 (B1/B2/B3) | ✅ | bos_metrics/capability_catalog/bos_discovery |

### 1.3 架构差距 (网关→编排大脑)
1. **计费缺失**: 仅 QPS 限流 (agora-bos-rates.yaml), 无用量计费/配额
2. **语义路由未全量启用**: resolve_with_capability 存在但 POC 路由仍主走 (91/5 连接率)
3. **声明/实现一致性治理**: bos-services 200 声明 vs 5 连接 vs 89 tools 三口径
4. **能力目录只读投影**: external_resources 聚合目录无写闭环

## 二、场景与功能对齐

### 2.1 核心场景覆盖
| 场景 | 现状 | 缺口 |
|---|---|---|
| agent → bos:// 调用 | ✅ 路由+准入 | 连接率低 (5/91) |
| capability 生命周期 (注册/度量/僵尸) | ✅ B1/B2/B3 | 无写闭环 |
| 网关健康监控 | ✅ /health+/metrics+面板 | 无告警主动通知 |
| MCP 工具消费 (cockpit bos/mcp) | ✅ | 7422 硬编码未 SSOT |

### 2.2 功能对齐待办
1. cockpit bos.py:672 硬编码 7422 → port-registry SSOT
2. scene-cards 补 agora BOS 网关场景卡

## 三、文档/配置/规则/依赖同步清单 (本次执行)

| # | 项 | 文件 | 现状 | 动作 |
|---|---|---|---|---|
| 1 | 子模块指针 | 主仓 projects/agora | d128c5f (P2) | ✅ **已由 PR #1061 完成** (7756362) |
| 2 | project-registry | docs/project-registry.yaml:52 | bos_services 196 | ✅ 更新 200 + 口径注明 |
| 3 | I0 callchain | docs/I0-AGORA-CALLCHAIN.md | 双进程未记录 + tools_bos 路径失效 | ✅ 补双进程统一 + /metrics + hashchain + 修路径 |
| 4 | AGENTS.md | AGENTS.md §8 | 仅 Phase 45 | ✅ 补 P1/P2 新能力 |
| 5 | cockpit 硬编码 | projects/cockpit/src/cockpit/commands/bos.py:672 | 7422 | ✅ 改 port-registry SSOT + SSE 优先 |
| 6 | scene-card | docs/scene-cards/ | 不覆盖 agora | ✅ 补 agora 网关场景卡 |
| 7 | CI submodules | .github/workflows/agora-ci.yml | recursive+continue-on-error | ⏸️ 保留 (已有保护, PR #906 显式 init 为可选优化) |

## 四、执行策略 (worktree 隔离)

### 4.1 变更拆分
- **主仓 A (文档+配置+指针)**: project-registry + I0-CALLCHAIN + AGENTS.md + scene-card + agora-ci.yml + submodule pointer → 1 PR
- **主仓 B (规则)**: governance-checks 如有 agora 相关规则更新 → 随 A 或独立
- **cockpit (子模块)**: bos.py 7422 SSOT → 独立子模块 commit + 主仓 bump
- **agora (子模块)**: 无代码改动 (复盘修复已合入 7756362)

### 4.2 执行顺序
1. **新起 worktree** (基于 main) → 主仓 A 分支
2. 更新文档/配置/规则/指针 (第 1-7 项)
3. 验证: doc-ssot-lint + gac-local-gate + 指针校验
4. PR 合入
5. cockpit 子模块独立处理

## 五、后续战略路线 (非本次执行)
- **P1**: backends 连接率 5/91 → 修复包缺失 + 补 admission 元数据
- **P2**: 用量计费/配额 (网关→编排大脑关键一步)
- **P3**: 能力目录写闭环 (外部资源注册→admission→路由)
- **P4**: 告警主动通知 (degraded → webhook/邮件)
