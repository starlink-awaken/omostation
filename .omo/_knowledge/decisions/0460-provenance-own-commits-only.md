---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-29
type: ssot
id: ADR-0460
related: ADR-0459, ADR-0422, ADR-0457
tags: [clone-lifecycle, provenance, commit-identity, security, threat-model]
---

# ADR-0460 — provenance 身份校验应只覆盖 clone 自身提交, 而非 frozen_root..HEAD 全区间

- **Status**: ACCEPTED（2026-09-29 principal 确认威胁模型取舍并批准实施；已落地于 `60f9e3eb5` / PR #4556）
- **Date**: 2026-09-29
- **Related**: ADR-0459（clone-lifecycle 管道三类阻塞，本文是其问题二「与多 agent 并发不兼容」的收敛方案）、
  ADR-0422（escape hatch / fingerprint）、ADR-0457

## 背景

`ADR-0459` 已定位：`verify_clone_provenance` 的最终判定包含

```python
commit_identities_match(repo_root, identity["frozen_root_sha"],
                        author["identity_digest"], "HEAD")
```

它要求 **`[frozen_root_sha, HEAD]` 区间内每一个提交的 author 与 committer 都等于
clone 绑定的身份**。而 `frozen_root_sha` 是 clone 建立时的 main。

### 闭环依赖

1. `provenance` 在 clone 建立时（**产生任何提交之前**）绑定 `frozen_root_sha`
2. 身份校验要求该 SHA 到 HEAD 之间所有提交均为绑定身份
3. 他人向 main 提交，会把**他们的提交插入这个区间**
4. clone 产生提交后，`provenance_late_binding` **禁止重绑**

**结论：管道仅在「clone 建立到 integrate 之间无人向 main 提交」时可用。**
2026-09-28 实测该区间内已有 3 个他人提交；在 6+ 并发 agent、main 约每 2 分钟推进一次的
本仓，该竞态无法稳定取胜。

### 为什么不能靠「重绑 provenance」解

`provenance_late_binding` 的存在有其道理：重绑会让「已签名后发生的篡改」无法与
「签名后的正常工作」区分。但换言之，**当前设计把「区间内出现他人提交」当成了篡改信号**，
而在本仓它只是常态。

## 决策方向

身份校验的**对象应是 clone 自身产生的提交**，而非它所处的时间区间。

### 候选方案

| | 做法 | 优点 | 风险 |
|---|---|---|---|
| **A** | 区间改为 `HEAD --not <mainline refs>` | 实现最小；语义正确 | mainline ref 缺失/被 force-push 时行为需明确定义 |
| **B** | identity 记录首个自身提交 | 区间精确 | **不可行**：provenance 必须早于任何提交绑定，无法预知 |
| **C** | 保留全区间，仅在检测到他人提交时告警不阻断 | 改动最小 | 仍不解决并发下的可用性，只是把硬失败降为噪声 |

**倾向 A**，但必须同时定义清楚：

1. `mainline refs` 取哪些（`origin/main` + identity 里的 `requested_revision`？）
2. 若某 ref 不可达或缺失 → **fail closed**，不得静默放行
3. 自身提交若 author 不符 → 仍**必须**拒绝（这是本检查的核心价值，不能被削弱掉）

## 威胁模型

收窄区间会放弃一项保证，须显式承认：

| 攻击者 | 收窄前 | 收窄后（A） |
|---|---|---|
| 能在 clone 内改代码但不能用绑定身份提交 | 拒绝 | **仍拒绝**（自身提交区间） |
| 能在 main 上直接推送 | 拒绝 | **放行**（其提交已不在自身区间） |
| 第三方在 main 混入提交 | 拒绝（误判） | 放行 |

第二行是本次收窄**唯一**实质性的能力变化。评估：能在 main 上直接推送的人，本来就能绕过
任何 clone 侧校验 —— 绕过路径不在这个检查的保护范围内。而当前设计对第三行的「误判」代价
是交付通道在并发环境下不可用。

**但这必须由 principal 显式确认，不由实现者默认。**

## 验收要求（实现时必须满足）

1. 自身区间内任一提交身份不符 → **拒绝**（回归测试须覆盖）
2. main 上他人提交 → **不阻断**（回归测试须覆盖）
3. mainline ref 不可达/缺失 → **fail closed**（回归测试须覆盖）
4. 在 6+ 并发 agent 环境跑通一次完整 `onboard → provenance → snapshot → changeset → integrate`
5. `transfer_commit_identities_match`（`agent-clone.py:2701`）同源问题一并处理

## 实施记录（2026-09-29）

已按本文方案 A 实施（PR #4556）：

- `commit_identities_match` 区间改为 `rev-list <head> --not <mainline refs>`
- `_mainline_refs()` 要求 `requested_revision` 与 `refs/remotes/<remote>/main`
  **全部可解析**，否则 `clone_mainline_ref_unavailable` fail closed；无 remote 同样拒绝
- 同源修复 `transfer_commit_identities_match`
- 三项契约测试（`tests/unit/test_clone_provenance_own_commits.py`），已验证有效性：
  还原为旧行为则契约 2 FAILED

### 落地时发现的约束

`git rebase` 会用**当前 git config** 重写 **committer** 身份。真实 clone 的 clone-local
`user.name/email` 必须等于绑定身份（`live_author_identity` 的硬性要求），否则 rebase 后
自身提交的 committer 会变成他人，校验随即失败。方案 A 的正确性依赖这一点。

## 不做的事

- 不放宽 `provenance_late_binding`
- 不改 claim 权威、fence 语义、发布栅栏（那是 ADR-0459 问题三）
- 不用 escape hatch 绕过（`ADR-0422` 明确：provenance 失配不是「门禁误伤」）
