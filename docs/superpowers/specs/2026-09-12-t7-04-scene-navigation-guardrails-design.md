---
title: 多 Agent 场景导航锚点与运行时防跑偏护栏机制设计
bet_id: BET-Y1Q4-T7-04
status: accepted
schema_version: specification/v1
spec_version: 1.0.0
value_indicator_policy: false
created: 2026-09-12
owner: governance-team
lifecycle: spec
last-reviewed: 2026-09-12
---

# T7-04 — Scene Navigation Anchor & Runtime Guardrails 设计

## 1. 问题

多 Agent 并发执行时, 场景旅程存在三类跑偏:

1. **意图漂移**: 任务委派方描述模糊, Agent 拿不到应挂接的场景锚点,
   在 67 张受管场景卡中盲目行动。
2. **能力越界**: Agent 调用场景能力面之外的写操作/工具 (CapabilityJail 缺位)。
3. **数据越界**: 写路径逃出场景允许目录沙盒 (DataScopeGuard 缺位),
   包括 symlink 逃逸。

跑偏在发生前不可见——缺少偏离度监控 (Drift Radar), 只能事后审计。

## 2. 非目标 (与 ledger non_goals 一致)

- 不废弃 66+ 张受管场景卡 YAML 定义 (只读消费 `scene-cards-v3.yaml`)。
- 不替代 Git worktree 隔离机制。
- 不阻断只读查询与探活行为 (circuit breaker: 探活类操作一律 warn 模式)。

## 3. 设计

### 3.1 场景导航锚点 (`projects/omo/src/omo/scene/anchor.py`, L2 内核)

- `SceneAnchorRegistry`: 注入式加载 `scene-cards-v3.yaml` (67 场景),
  按 scene_id 索引; 暴露 `get(scene_id)`。
- `recommend(text, top_k=3)`: 确定性意图推荐——对场景 name/scene_id/domain/
  capability_refs 做加权关键词评分, 返回 `[{scene_id, score, confidence}]`。
  零模型调用; confidence = score/满分, 无命中时返回空列表 (诚实失败)。
- `bind(session_id, scene_id)`: 校验场景存在且 lifecycle ∈
  {draft, shadow, assisted, supervised, routine}, 签发锚令牌:
  `{anchor_id, session_id, scene_id, lifecycle, capability_refs,
  allowed_roots, issued_at, digest}`; digest = sha256(规范 JSON)。
- `verify(token)`: 重算 digest 防篡改; 场景被移除时报 `scene_revoked`。

### 3.2 运行时护栏 (`projects/omo/src/omo/guardrail/enforcer.py`)

- `CapabilityJail`: 依据锚令牌 capability_refs 派生写能力白名单;
  `check(tool, token)` 三态:
  - `allow`: tool ∈ 白名单;
  - `warn`: 只读/探活类 (`get|list|status|probe|search|read|health`) ——
    永不阻断 (circuit breaker 铁律);
  - `deny`: 其余, 附 reason。
- `DataScopeGuard`: `check_path(path, token, mode)`——write 模式要求
  realpath ∈ allowed_roots; symlink 解析后逃逸 allowed_roots 一律 deny;
  read 模式仅 warn 不阻断。
- `DriftRadar`: 滑窗动作轨迹 (tool, path, ts), 偏离度 =
  w1×越权尝试 + w2×越界路径 + w3×域偏移 (动作域 ≠ 场景域);
  `evaluate(actions, token)` → `{drift_score, decision: pass|warn|intercept}`;
  超阈值即 `intercept`。纯函数, 无外部依赖。

### 3.3 BOS 网关 facade (`projects/agora/src/agora/server/tools_scene.py`, L3)

- `SERVICE_URI = bos://scene/anchor`; 子操作 `recommend|bind|verify|guard`。
- L3 织层 `special: true` 可调用任何层: facade 优先 in-process 动态导入
  omo 内核模块; omo 不可用时返回 `kernel_unavailable` 诚实失败
  (同 voice.py `needs_asr_backend` 先例), 绝不在 facade 层伪造护栏判定。
- 不新增 agora→omo 的 pyproject 硬依赖边 (避免层契约 edges 变更);
  运行时动态导入 + 明确失败语义。

### 3.4 端到端验证

`projects/omo/tests/unit/test_scene_guardrail_anchor.py`:
对 `scene-document-review` 与 `scene-engineering-delivery` 两张真实场景卡
跑 "锚定 → 正常轨迹放行 → 漂移注入 → 100% 拦截" 四段仿真;
漂移注入覆盖: 越权写工具、allowed_roots 外写路径、symlink 逃逸、
跨域动作序列四类; 正常轨迹含探活操作, 断言零误报阻断。

## 4. 完成判据 (映射 ledger done_when)

| done_when | 本设计落点 |
|---|---|
| bos://scene/anchor 握手网关 + 意图推荐解析 | §3.1 + §3.3 |
| CapabilityJail 越界拦截 + DataScopeGuard 目录沙盒 | §3.2 |
| Drift Radar 仿真漂移场景 100% 拦截 | §3.2 + §3.4 仿真断言 |
| document-review / engineering-delivery 端到端闭环 | §3.4 |

## 5. 风险与回滚

- 纯新增模块, 不改既有执行链; 回滚 = revert 单 PR。
- 护栏默认仅在被显式锚定的会话内生效, 不影响未锚定存量路径。
