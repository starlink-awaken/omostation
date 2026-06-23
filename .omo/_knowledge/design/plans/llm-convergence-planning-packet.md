---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# LLM Convergence Planning Packet

> 日期: 2026-05-30 | 版本: v1.0 | 状态: future-gated planning packet
> 来源: `llm-convergence-requirements.md`
> 放置策略: `dual_track`

---

## 1. 规划结论

LLM 收敛按 **dual_track** 落地：

1. **Phase 2 尾波** 只做最小前置项，确保 LiteLLM 真正可用、控制面知道怎么验证。
2. **Phase 3 主包** 再做默认路由切换、碎片组件收敛、统一环境变量和回退策略。

这样可以避免在 Phase 2 尾声一次性推太多跨项目 LLM 迁移，同时又不给 Phase 3 留下“先补基础设施、再谈能力”的隐形阻塞。

## 2. Phase 2 尾波（gated prerequisites）

### W0. LiteLLM baseline 可用性

目标：确认 LiteLLM 不是“装着但没接”的摆设。

- 收敛 provider 配置，保证 `:4000/health` 有健康模型
- 用 `curl /v1/chat/completions` 验证至少一个模型可用
- 将 health/model smoke test 纳入 `.omo` 的后续执行验证清单

**2026-05-30 实际落地结果：**

- provider registry 已切到 `cc-switch`
- 本地统一 proxy 仍使用 `LiteLLM`
- quota / 额度观察面使用 `CodexBar`
- 当前已验证一条健康链路：`cc-switch(DeepSeek Claude path) -> LiteLLM(:4000) -> claude-3-5-sonnet`

### W1. agent-runtime 环境切换验证

目标：用最小代价打通第一条真实收敛路径。

- 不改 agent-runtime 业务代码
- 只通过 `AGENT_RUNTIME_BASE_URL` / `AGENT_RUNTIME_API_KEY` 指向 LiteLLM
- 形成 smoke evidence，作为后续更多组件迁移的基线样板

**2026-05-30 实际落地结果：**

- `projects/agentmesh/config/gateway.yaml` 已补齐 runtime `models` 段
- `claude` 默认路由现在优先走本地 `litellm`
- `projects/agentmesh/packages/gateway/src/config/gateway.yaml` 同步对齐，便于后续包级默认配置保持一致

**Phase 2 出口**：完成 W0/W1 后，才允许把“LLM convergence 主包”正式排进 Phase 3 执行。

## 3. Phase 3 主包（main convergence package）

### Track A. gbrain 默认路由收敛

- 扩展 `litellm-proxy.ts` 的 touchpoint 定义
- 让 chat / expansion / embedding 默认优先走 LiteLLM
- 保留其他 provider 作为 fallback 选项

### Track B. Minerva 与碎片组件收敛

- Minerva CLI 去除硬编码 provider URL
- sophia / ssot / ontoderive / metaos 改为环境变量驱动的统一入口
- 保持“env 未设时兼容旧行为”的回滚能力

### Track C. 验证与故障策略

- 补全 LiteLLM down / provider fail / fallback smoke tests
- 更新现有 Phase 1/2/3 集成验证中的 LLM 健康判断方式
- 为后续 cost tracking / routing policy 做留口，但不在本包内强做 UI

### Track D. 环境变量标准化

- 统一 `LLM_PROVIDER / LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`
- 逐步吸收各组件现有的 provider-specific env var
- 这一块放在主包后半程，避免一开始就做全局变量大迁移

## 4. 推荐拆分为 4 个 planning workstreams

| Workstream | 默认挂载 | 目标 |
|------------|----------|------|
| WS1 LiteLLM baseline | Phase 2 tail | 验证 proxy 可用、provider 对齐、health/model smoke |
| WS2 Runtime route seam | Phase 2 tail | 打通 agent-runtime → LiteLLM 的最小闭环 |
| WS3 gbrain + Minerva convergence | Phase 3 | 处理默认路由、fallback、硬编码清理 |
| WS4 Fragment cleanup + env standardization | Phase 3 | 收敛碎片组件与统一环境变量 |

## 5. 进入 `.omo/tasks/active/` 前的 gate

以下条件缺一不可：

1. LiteLLM 至少一个 provider 已稳定可用
2. `.omo` control-plane 当前 schema / dispatch / review gate 保持绿色
3. 相关组件的 owner 和验证入口已明确
4. L2/L3 风险动作仍遵守 approval gate，不因 LLM 收敛绕过治理

**当前 gate 状态（2026-05-30）：**

- Gate 1: ✅ 已满足
- Gate 2: ✅ 已满足
- Gate 3: ✅ Phase 3 foundation track 已可分批启动
- Gate 4: ✅ 仍由 Safe Mesh / RBAC 约束高风险动作

## 6. 与现有规划的关系

- `llm-convergence-requirements.md`：需求源，不直接下发 execution
- 本文件：拆解后续 wave / workstream / gate 的 planning packet
- `phase3-task-specs-v2.md`：后续若正式立项，应从本包抽取成具体 sprint/wave task

## 7. 建议的下一步

优先级建议：

1. 先把 WS1 / WS2 写成 **Phase 2 尾波 gated candidate**
2. 再把 WS3 / WS4 作为 **Phase 3 foundation track**
3. 等 LiteLLM baseline 真实可用后，再决定是否把 gbrain default route 前提到 Phase 2 尾波
