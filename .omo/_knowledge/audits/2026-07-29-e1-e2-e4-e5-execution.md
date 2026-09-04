---
lifecycle: history
owner: governance-team
last_updated: "2026-07-29"
---
# E1/E2/E4/E5 执行记录 (人类 delegated decisions 授权)

> 上位: 2026-07-29-human-delegated-decisions.md (人类授权 E1-E5)
> E3 例外二清单单独产出 (见 e3-exception-two-list.md)
> D4 四项不覆盖 (G-DEL.5b/物理多机/KOS/BET-3b90)

## E2 · check-scenario-growth 接真实合并门 ✅ (实测 W15 拦截)

**验收 (用户强调: 模拟 W15, 合并路径被拦)**:
- 模拟 W15: 写 ADV79-w15-cap-test.yaml (编号 79 > cap 77)
- 跑合并门 `gac-local-gate --strict` (CI 真门, --no-verify 绕不了)
- **实测结果**:
  - `[FAIL] check-scenario-growth :: bin/gac/check-scenario-growth.py`
  - `ADV79-w15-cap-test.yaml [adv_cap_exceeded] ADV 编号 79 > 上限 77`
  - `GaC local gate: FAIL`
  - **strict exit code: 1** (合并被拦 ✅)

**结论**: 门真接合并路径, W15 进不来. 上一轮 W14 没拦住 (门注册但不在合并路径) 已修.
--no-verify 绕本地 pre-commit, 但 CI gac-gate.yml 跑 strict, **绕不了合并门**.

## E1 · 回滚 #592 (人类 D1 授权) — 方案 + 冲突报告

**决定**: 回滚 a86cbe7ae (#592 多机, 违反 ADR-0247 DEFERRED).

**执行状态**: 🔴 **未直接执行 revert** (冲突 + 破坏性, 报告方案):
- #592 (a86cbe7ae) 改 `projects/runtime` submodule pointer (1 行)
- 当前 working tree `projects/runtime` **也 dirty** (M, 我的 pointer 改动)
- `git revert a86cbe7ae` 会与 dirty runtime **冲突**

**回滚方案 (待人类确认执行)**:
1. 先理清 runtime pointer 状态 (我的 vs #592 的)
2. stash dirty + `git revert a86cbe7ae --no-edit` + unstash
3. 或走 branch: `git checkout -b revert-592-deferred` → revert → PR
4. **push main 是 outward-facing, 需人类最终确认** (CLAUDE.md §6)

**ADR-0247 DEFERRED 状态**: ✅ **未被侵蚀** (line 23/34 仍 DEFERRED, #592 是违规开线非侵蚀 ADR).

**agent 立场**: D1 人类授权回滚, 但 revert+push main 破坏性 + runtime 冲突, 报告方案待人类确认执行时机.

## E4 · 目标重设 (D2) + BRIEF/门禁同步

**新目标 (D2)**:
- 月度真实任务: **15** (8 月, 原 30/45/60 作废)
- 完成率: **≥85% 不变**
- 协作管线适用面: **仅"简单独立批量"** (思考性任务单 agent)

**BRIEF/门禁同步**:
- 🔴 旧爬坡表 (30/45/60) **作废, 不得作门禁依据**
- BRIEF 协作仪表须反映新目标 (月 15 + 适用面)
- 门禁 (check-dual-track-purity / scenario-track-purity) 不变 (构造场景不计产能轨)

**产能轨当前 (T1 去污后)**:
- 真实 done (有 PR): 9 (保守) / 30 (宽松含疑似)
- 完成率: 81.8% (保守) / 93.75% (宽松)
- 月 15 目标: 当前 9 < 15 (保守不达标), 但 8 月还有时间

## E5 · ADR 落档

**本文件** (2026-07-29-human-delegated-decisions.md): 人类授权凭据, 已存 `.omo/_control/`.

**D2 amend ADR-0247** (适用面边界):
- ADR-0247 主轴地位保留 (协作优先)
- **amend 适用边界**: 协作仅"简单独立批量", 非思考性任务默认
- 依据: R1 纯 text (思考性 0.5-0.6x) + T1 产能污染
- 🔴 待落档: ADR-0247 amend (agent 不擅自改 ADR, 需走 ADR 流程或人类确认)

## D4 (不覆盖, 列记)

以下四项**本次授权不覆盖**, agent 不得据本文件执行:
1. G-DEL.5b 涌现类实装 (须 kill-switch 人类评审先行)
2. 物理多机达标宣称 (须真机 + 人类宣布)
3. KOS 新数据源接入
4. BET-3b90 产品走查 (属 human product team)

## 🔴 红线
- E2 实测 W15 合并被拦 (非文档说)
- E3 例外二单独产出 (不跳过)
- D4 不覆盖 (不执行)
- E1 revert 待人类确认 (破坏性 + 冲突)
- E5 ADR amend 不擅自改 (走流程)

## References
- 2026-07-29-human-delegated-decisions.md (D1-D4 + E1-E5)
- R1 纯 text · T1 去污 · E3 例外二清单
