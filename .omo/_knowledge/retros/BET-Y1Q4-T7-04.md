---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T7-04
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-12
type: ephemeral
---

# BET-Y1Q4-T7-04 retro — 场景导航锚点与运行时防跑偏护栏

## What changed

- **`projects/omo/src/omo/scene/anchor.py`**（新）：SceneAnchorRegistry 只读
  消费 scene-cards-v3.yaml（67 场景），确定性意图推荐（关键词加权评分，
  零模型调用，无命中诚实空）、锚令牌签发/校验（digest=sha256 规范 JSON
  防篡改，场景撤销检测）。
- **`projects/omo/src/omo/guardrail/enforcer.py`**（新）：CapabilityJail
  （capability_refs 派生写能力白名单，越界 deny）、DataScopeGuard（写路径
  allowed_roots 沙盒 + normpath/realpath 对比识别 symlink 逃逸）、
  DriftRadar（滑窗加权计分：越权×2 + 越界×2 + 跨域×1，≥3 intercept）、
  GuardrailEnforcer 统一裁决。
- **`projects/agora/src/agora/server/tools_scene.py`**（新）：BOS facade
  `bos://scene/anchor`（recommend/bind/verify/guard），动态导入 omo 内核，
  不可用时 `kernel_unavailable` 诚实失败，绝不伪造护栏判定。
- **测试**：omo 26 用例 + agora 6 用例（含内核缺失诚实失败断言）。

## Done when 逐条

| 判据 | 结果 |
|------|------|
| bos://scene/anchor 握手网关 + 意图推荐解析 | ✅ facade 四动作 + 确定性推荐（e2e 实测真实卡） |
| CapabilityJail 越界拦截 + DataScopeGuard 目录沙盒 | ✅ 三态判定 + symlink 逃逸拦截（单元实测） |
| Drift Radar 仿真漂移 100% 拦截 | ✅ 四类注入（越权/越界/symlink/跨域累计）全拦截，26 用例断言 |
| document-review / engineering-delivery 端到端 | ✅ 两张真实场景卡四段仿真：正常轨迹零误报 + 漂移全拦截 |

## Circuit breaker 遵守

只读/探活类（get/list/status/probe/search/read/health/…）一律 warn 模式
永不硬阻断——单元与 e2e 均有显式断言（探活路径越沙盒仅 warn）。

## Verify 实测（run 20260912T080307Z-project-code-change-eded1968）

- `pytest tests/unit/test_scene_guardrail_anchor.py`（projects/omo）→ 26 passed
- `pytest tests/test_tools_scene_anchor.py`（projects/agora, --with ../omo）→ 6 passed
- `bet-ledger.py lint` → OK, 405 bets, no errors

## Rollback

纯新增模块（2 个 omo 子包 + 1 个 agora facade + 2 个测试文件）+ ledger
条目行级更新；回滚 = revert 单 PR，无既有执行链改动。

## Lessons

- 受管场景卡的 capability_refs 因卡而异，e2e 不能假设写能力存在——
  正常轨迹按锚令牌实际授予面派生写工具，无授予时退化为纯只读探活。
- claim 的 --path 必须 ⊆ ledger write_surfaces：交付前先对齐写面清单
  （本次补了 agora 测试 + ledger 自身两行），否则 WORK_PACKET_SCOPE_MISMATCH。
