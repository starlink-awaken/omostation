---
status: needs-human
lifecycle: history
owner: governance-team
last_updated: "2026-07-29"
---
# P86 T3: W 波驱动源定位 (三轮未果, 诚实记录找不到)

> 上位: goal T3 (找真正驱动源, 三轮未果这次定位)
> 🔴 红线 (T3): 找不到驱动源就编解释 = 违规. 本文档如实记录"找不到".

## 调研范围 (本轮第三轮)

### 1. ~/.claude/ (Claude Code 平台)
- `settings.json`: 提 `/schedule creates remote agents (triggers) that execute on a schedule`
- `cache/changelog.md`: 提 `/loop`, `CronCreate` 任务, `CLAUDE_CODE_DISABLE_CRON` 环境变量
- **线索**: Claude Code 有定时机制 (/schedule / /loop / CronCreate)
- **但**: 无具体 "W 波" 定时任务配置 (settings.json 无 wave/W/ADV cron 条目)

### 2. agent profile (~/.claude/agents/ + .claude/agents/)
- GeminiResearcher / Algorithm / ... 无 W 波续跑逻辑
- 无 agent profile 嵌 "自动进 W 波" 或 "ADV 生成"

### 3. workflow 模板 (.omo/ + ~/.claude/)
- P84 longplan 自动推进条款已 🛑 废止 (S2 确认)
- 无其他模板嵌 auto-advance / W 波续跑
- history.jsonl 是**用户历史输入** (含 /goal), 非自动驱动

### 4. Cowork 定时 (~/Documents/驾驶舱/_control/)
- **空** (无 scheduled/cron/timer 条目)

### 5. history.jsonl 线索 (弱)
- `Read .omc/state/team/ecosystem-debt-burnd/workers/worker-N/inbox.md execute now`
- 这是 **.omc** (非 .omo), 且是用户历史 session 输入, 非自动

## 候选驱动源 (无法确认, 列举不编)

| 候选 | 证据 | 可信度 |
|------|------|--------|
| Claude Code /schedule / CronCreate | settings + changelog 提机制存在 | 🟡 可能 (但无具体 W 波配置) |
| agent 响应式 (我) | 每次 /goal 谈协作/ADV, agent 可能手动加 | 🟡 可能 (但系统改动非我手) |
| 系统/linter 自动 | scenario_lib 多次被改 (加 _synthesize_*), 非我操作 | 🟡 可能 (linter/hook 触发) |
| 隐藏 cron / hook | 未找到, 但可能在我未查的位置 | 🟡 不能排除 |

## 🔴 诚实结论: 找不到明确驱动源

> **三轮调研 (R2 改 longplan + S1 装门 + T3 查 scheduled/profile/workflow/Cowork) 均未定位
> "是谁在派 W 波".** W13 在 longplan STOPPED + 门装上后**仍照落**, 说明驱动源在我未找到的地方.

**不编解释** (T3 红线). 候选都是"可能", 无定论.

## 送卡 (P86 §F, T3 解锁人类协助)

请人类协助定位驱动源:
1. **Claude Code /schedule / CronCreate**: 检查是否有隐藏的 W 波定时任务 (用户侧 /schedule 列表)
2. **系统/linter hook**: 检查 PostToolUse/SessionStart hook 是否触发 ADV 生成
3. **外部 cron / launchd**: 检查系统级定时 (本机或 CI)
4. **别的 session / agent**: 是否有并发 session 在派 W 波

agent 侧已穷尽 (longplan/gate/redline/profile/workflow), 需人类从平台/系统层查.

## T3 状态
- ✅ 调研完成 (~/.claude/ + agents + workflow + Cowork + history)
- 🔴 **驱动源未定位** (诚实, 不编)
- ⬜ 送卡人类协助 (平台/系统层)

## References
- goal T3 (找驱动源, 找不到如实说)
- R2 (改 longplan) / S1 (装门) — 前两轮未拦住 W13
- T2 (门扩覆盖, 防 W14 detector 形态绕过)
