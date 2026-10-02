---
title: clone-lifecycle 交付管道的 fail-closed 门与恢复路径
type: reference
owner: governance-team
last-reviewed: 2026-10-02
---

# clone-lifecycle 交付管道的 fail-closed 门与恢复路径

`bin/gac/clone-lifecycle.py` 的每一环都会 fail-closed。本文按**执行顺序**列出
会遇到的门、它们的触发条件、以及**怎么恢复**——目的是让它们不再是「只能逐门试错
才能定位的墙」。

> 本文的权威提案见 [ADR-0459](../../../.omo/_knowledge/decisions/0459-clone-lifecycle-pipeline-blockers.md)
> 问题三④ 与验收第 5 条。**放宽任何一道门都不是本文的解法**; 本文只描述
> 门本身与恢复步骤。

## 0. 先判断你在哪个态

`integrate` 的行为由 **claims authority 的激活态** 决定, 这是最容易踩空的一步:

| `activation_mode` | `integrate` 行为 |
|---|---|
| `unactivated` | 跳过 legacy fence, 直接进入推送 |
| `shadow-active` | **强制** `enter_legacy_publish_fence` |
| 其他 | 拒绝(`claims_authority_activation_invalid`) |

本机当前是 `shadow-active`, 因此**第 4 节的 fence 门必然命中**。

## 1. `clone_identity_required` / readiness 非 ready

**触发**：`readiness` receipt 的 `status` 非 `ready`。判定只看 `degraded_checks`。

**最常见成因**：`workflow_entrypoint_check` 或 `managed_python_probe` 超时被记为
`degraded` + `required: true`, 进而在 `degraded_checks` 里留下条目。

**已修**（2026-09-30, PR #4579）: 这两个探针的超时改记 `unverified` + 非阻断,
且预算可调(`AGENT_CLONE_ENTRYPOINT_TIMEOUT` / `AGENT_CLONE_GIT_*_TIMEOUT`)。
`OSError`(进程根本起不来)仍保持阻断。

**恢复**：确认 `degraded_checks` 为空再继续。若仍非空, 看该条目的 `detail`。

## 2. `clone_provenance_mismatch`

**触发**：provenance receipt 是**创建时**凭证; 取入任何提交、或 rebase 改变
committer 之后, 重验即失配。

**恢复**：不要试图重签 —— `provenance_late_binding` 会拒绝。正确做法是
**重跑整个 onboard**, 让 receipt 与当前状态重新绑定。

## 3. `changeset_claim_scope_violation` / `changeset contains unclaimed paths`

**触发**：changeset 含未被 claim 覆盖的路径。两个常见成因:

1. **claim 记在错误的 run 上**。`claim` 归属是按 run 记录的, 若用扫描「第一个
   active run」而非 `agent-workflow start` 返回的 run id, claim 会落到上一轮遗留
   的 run 上, 校验器读到的就是旧 claim。
2. **payload 混入未声明路径**。例如工作树里带了并发 agent 的子模块指针漂移。

**恢复**：用 `start` 返回的 run id 建 claim; 用
`git diff --name-only origin/main..HEAD` 核对 changeset 的 `changes` 与 claim 的
`claimed_paths` 是否**完全一致**。校验结果看 changeset 的 `claim_verification.all_covered`。

## 4. `legacy_publish_fence_required: LEGACY_FENCE_CONTEXT_UNAVAILABLE`

**这是当前本机的实际阻断点。**

### 触发条件

`bin/gac/clone-lifecycle.py:1594` —— 当 `activation_mode == "shadow-active"` 时,
`integrate` **强制**调用 `enter_legacy_publish_fence`, 后者从 changeset 的
verification dict 读取 `claims_authority_fence_context`
(`clone-lifecycle.py:1296`); 该键缺失即抛此错。

### 为什么它必然缺

- 全仓 `claims_authority_fence_context` **只有一个读取方**(`clone-lifecycle.py:1296`),
  **没有写入方**。
- 承载 changeset 的 `build_claims_authority_shadow_projection()` 在
  `bin/gac/agent-clone.py:3536`, 其 docstring 明确:
  *"Redacted observer projection only — **never authority and never publication grant**"*
- 也就是说, 管道当前只有**观测投影**, 没有**发布授权**通道, 两者之间没有桥。

本机 authority 的激活回执亦为 `publishable: false` / `security_level: R0_COOPERATIVE`
(`projects/omo/src/omo/workflow/claims_authority.py:1368,1646` 硬编码)。

**结论: 在 `shadow-active` 态下这道门不可满足, 且这是设计行为, 不是故障。**

### 可获取的上下文来源

`lifecycle-human-approval.json`
(`~/.local/share/zhixing-dashboard/claims-observation/`) 是**证据存档, 不被任何
代码读取**——续期它不会改变任何运行时行为。ADR-0455 的执行门第 3 条提到的
`DEC-20260923-CLAIMS-LIFECYCLE-R0-01` 窗口已于 `2026-09-25T01:47:16Z` 到期。

**没有任何非破坏性的停用路径**: authority 的 `activation_state` 存于 SQLite 的
`activation` 表(`_activation_meta()`), 删除 `activation-witness.json` **不会**翻转它;
源码中也不存在 deactivate/rollback 动词。

### 恢复步骤

1. **本机现状下的可行动作**: 走**常规 PR 流程**交付。ADR-0459 结论原文:
   「在问题二④修好前, `clone-lifecycle integrate` 在本仓不具备可用性, 应走常规 PR 流程」。
2. **要恢复管道能力**, 需先补上观测→授权的桥。该桥的契约(谁签发、绑定什么范围、
   效果上限、失效条件、可回滚性)**尚未成文** —— 在其成文并评审前, 不要绕过这道门。
3. **不要**为了让它通过而修改 `activation` 表或删除 authority store ——
   ADR-0455 的 forbidden 列表明确包含 `no historical receipt mutation`。

## 5. `claims_authority_revision_unavailable`

**触发**：claims authority 记录的 trusted main revision 不在 writer clone 里。

**恢复**：`git -C <clone> fetch origin main` 后重试。报错原文即已给出这条指引。

## 6. `root_rewind_or_diverged`

**触发**：candidate root 不是 snapshot baseline 的后代。

**恢复**：snapshot 必须在 `origin/main` 上取(先 `git checkout --detach origin/main`),
基线才是 main 的祖先; 在交付分支上直接 snapshot 会必然触发此错。

## 7. `output_collision`

**触发**:`--output` 目标已存在, 且内容不同。

**恢复**:换一个 `--output` 路径。**不要**复用旧路径 —— 旧 receipt 会与新的
delivery attempt 不匹配, 报 `identity_mismatch`, 比原错误更难诊断。

## 排障顺序建议

管道的失败是**串行**的: 前一道门没过, 后面的错误没有意义。逐门推进时按
1 → 7 顺序确认, 不要跳步猜测。
