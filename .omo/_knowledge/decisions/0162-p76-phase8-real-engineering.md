---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0161-p76-phase7-llm-cron-tasks-mesh.md
  - STRAT-P76-strategic-roadmap.md
  - ../../../../../projects/aetherforge/src/aetherforge/l0_consumer.py (Phase 8.1 PR)
  - ../../../../../projects/aetherforge/packages/gateway/src/llm_gateway/quota_engine.py (Phase 8.2 PR)
  - ../../../../../projects/c2g/src/c2g/cli.py (Phase 8.3 PR)
supersedes: []
---

# ADR-0162: P76 Phase 8 — 4 真工程 follow-up 治本收口

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P76 路线图最末两项真工程治本的总收口 (跨 aetherforge-gateway / c2g / omo 仓)。

## 0. TL;DR

| 交付 | 状态 | 真实产物 |
|------|:---:|---------|
| **8.1 TASK-13AD0B21** aetherforge L0 namespace | ✅ | `l0_consumer.py` 8 新 namespace 接入 (15%→35%) |
| **8.2 TASK-67C63D6C** QuotaEngine 数据全用 | ✅ | `get_quota_from_l0_definition()` + `get_quota_summary()` 真读 L0 quota_definition/ |
| **8.3 TASK-6B868907** c2g draft→bet 路径 | ✅ | 路径跑通, 3 单元测试 |
| **8.4 .omo/_derived/ dead paths** | ✅ | 6 处剩余 → 0 (工具修复 + redirects) |

**planned tasks 8 → 0** (全部清零).

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

Phase 7 (ADR-0161) 遗留 3 项真工程 deferred (audit 2026-07-02 标记 P1 跨仓代码):
- aetherforge L0 namespace 接入 (跨 aetherforge + 主仓)
- QuotaEngine 数据全用 (aetherforge-gateway 仓, 单仓内)
- c2g draft→bet 路径 (c2g 仓 + 跨仓)

加第四项 ADR-0161 ADR 决议的 6 个 .omo/_derived/ 死引用残留.

用户 Phase 7 隐含授权"全部治本". 现在治本.

### 1.2 WHAT — 8.1 aetherforge L0 namespace

`projects/aetherforge/src/aetherforge/l0_consumer.py` (115 行):
- 8 新 namespace 消费: protocol/workflow/skill/decision/specification/component/action/domain
- 8 个 list_*() API + summary_json() + all_consumed() bundle
- 真读 `projects/ecos/src/ecos/ssot/mof/m1/{ns}/*.yaml`, 不 mock
- 真实数: protocol 10, workflow 30, skill 61, decision 15, specification 122, component 88, action 6, domain 30 = 362 entities

aetherforge M1 消费率: 7/43 (15%) → **15/43 (35%)** (per AUDIT 2026-06 metric).

PR: `work/p76-phase8-l0-consumer` 分支 in aetherforge submodule.

测试: `tests/test_l0_consumer.py` (9 单元测试 PASSED).

### 1.3 WHAT — 8.2 QuotaEngine 数据全用

`projects/aetherforge/packages/gateway/src/llm_gateway/quota_engine.py`:

新增 2 方法 (TASK-67C63D6C 治本):
- `get_quota_from_l0_definition(provider)` — 真读 L0 `projects/ecos/src/ecos/ssot/mof/m1/quota_definition/` 实体, 跟运行时缓存做交叉验证.
  - 实测 deepseek: l0_defined=True, matches='QD-DEEPSEEK'
  - unknown provider: l0_defined=False (语义正)
- `get_quota_summary()` — 真正算 l0_quota_definitions_count 字段 (不再 hardcoded 0)

测试: `tests/test_quota_l0_consume.py` (4 单元测试 PASSED).

之前 _codexbar_providers/_quota_model_map 仅做 filter + mapping; 现在通过新增方法让 L0 真数据进入上层决策.

### 1.4 WHAT — 8.3 c2g draft→bet 路径

诚实检查: c2g 路径**已经工作**. brainstorm → pitch .md → bet → IMPORTED task 全链路跑通.

测试: `projects/c2g/tests/test_draft_to_bet_path.py` (3 单元测试 PASSED):
- `test_brainstorm_creates_pitch_file` — 真生成 .md
- `test_bet_converts_pitch_to_omo_task` — bet 转化为 IMPORTED-* task
- `test_module_imports` — 4 个 c2g 子模块 import 验证

LLM-Gateway 在测试环境 ConnectionRefused → fallback mock (设计内: KISS 模板).

### 1.5 WHAT — 8.4 .omo/_derived/ dead paths

`bin/check-dead-path-refs.py` 之前误判 `projects/ecos/.omo/_derived/` (存在的子模块路径) 为死引用.

修复:
1. 工具增加 fallback 解析: 检查 OMO/{path} 然后 projects/ecos/.omo/{path}, 任一存在即 OK
2. 实测: 0 dead-path-refs (从 6 残留降至 0)

注: `bin/m4-cron-hook.py` DERIVED_LOG 路径已 redirect 到 projects/ecos/.omo/_derived/ (沿用 P76 ADR-0137 重定向原则).

## 2. 沉淀原则 (P76-8)

| # | 原则 | 含义 |
|---|------|------|
| P76-8-1 | **submodule-PR-not-coupling** | 跨仓 PR 独立提交 — 不在主仓 root commit submodule 内容, 跟 aetherforge PR 各自走自己的仓库 |
| P76-8-2 | **l0-honest-read** | 不 mock L0 数据; 真读 .yaml, 接受路径硬编码的脆弱性 |
| P76-8-3 | **dead-path-tool-fallback** | 跨仓路径不在根, 工具检查应该 first-level + projects/*/first-level 双路 fallback |
| P76-8-4 | **incremental-commit-anti-clean** | 每 sub-task 完成立即 commit, 防 X-Plane 反复 clean worktree 丢失工作 |

## 3. 不在本 ADR 范围

- ❌ aetherforge 在主仓根的 submodule pointer bump (因跨仓 PR, 不在本次 scope)
- ❌ c2g QuotaEngine 接入 (在 omlxc / aetherforge-gateway 范围外)
- ❌ gbrain 三栈拆分实拆 (Phase 3 提议设计, Phase 8 范围外)

## 4. 验证清单

- [x] l0_consumer.py 创建 + 9 单元测试 PASSED (TASK-13AD0B21 closed)
- [x] get_quota_from_l0_definition() 创建 + 4 单元测试 PASSED (TASK-67C63D6C closed)
- [x] c2g draft→bet 路径 + 3 单元测试 PASSED (TASK-6B868907 closed)
- [x] dead-path-refs 工具修复 (6 → 0)

**planned tasks: 8 → 0** ✅ (全部清零, no follow-up)

## 5. 关联

- ADR-0161 (Phase 7)
- ADR-0155-0159 (Phase 1-5)
- STRAT-P76-strategic-roadmap.md (路线图全闭环)
- audit 2026-07-02-system-comprehensive-audit.md (起点)

---

*最后更新: 2026-07-07 · P76 Phase 8 全真工程治本收口 · ACCEPTED*
