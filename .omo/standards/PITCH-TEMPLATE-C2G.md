---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# C2G v4: Strategic Pitch Template

> **使用说明**: 此模板在 Sandbox (发散区) 使用。代替传统的 PRD 和繁琐的 Jira Backlog。
> 生成的 Pitch 需提交给 Betting Table（或 CEO 自我审批），如果下注成功 (Bet)，则带入 OMO 执行并分配 `context_uri`。

---

## 1. 核心叙事 (The Narrative)
*(NCT 框架中的 Narrative。1-3 句话说明为什么在这个周期要做这件事，以及对系统/用户的宏观战略价值是什么。)*
> 示例：目前 OMO 缺乏前置战略牵引，导致底层 Agent 容易陷入死胡同。我们需建立一套从宏观到微观的下注机制。

## 2. 待解痛点 (The Problem)
*(具体遇到了什么痛点？提供用例和场景。)*
> 

## 3. 资源胃口 (The Appetite)
*(你最多愿意在这件事上投入多少时间和精力？如果超过这个阈值，必须强制 Yield 止损。)*
> 示例：半天 / 1个周末 / 2周。
> **Appetite:** [填写时限]

## 4. 粗粒度方案 (The Solution / Fat Marker Sketch)
*(不要写具体的代码实现。描述流程、交互或组件边界。越粗越好。)*
> 

## 5. 兔子洞防范 (Rabbit Holes)
*(预判在执行时可能会掉进去的深坑。提醒 Agent 在这里要格外小心，不要过度工程。)*
> 

## 6. 绝对不做的边界 (No-Gos)
*(划定范围。明确指出哪些相关功能在此次 Bet 中绝对不要触碰。这是防患范围蔓延 (Scope Creep) 的最强武器。)*
> - 不做：
> - 不碰：

---
*状态区 (System Auto-Updates)*
**Bet Status**: `[Draft | Bet Placed | Yielded | Done]`
**Context URI**: `bos://memory/sandbox/pitches/Pitch-ID.md`
**Write-back Logs**:
*(执行期 Agent 完成 Task 后，利用 `mof-extract` 会将记录回写于此)*
