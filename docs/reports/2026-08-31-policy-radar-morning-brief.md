---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
bet_id: BET-Y1Q4-T7-03
---

# Policy Radar 每日晨报 — implementation evidence

## 交付

- **bin/bc-os/policy_radar.py**（引擎，标准库零依赖）：5 信源白名单（卫健委/
  医保局/工信部/arXiv×2）→ 规则打标（5 业务标签 + 政策文书词 + 噪音惩罚）→
  评分排序（每源 top3 / 总量 ≤15）→ JSON+Markdown 产物 + cache.json 快照
- **cockpit brief --morning**（brief.py 扩展 + cli dispatch 分流）：渲染当日
  晨报（Rich 面板，降级标注）
- 研判 v1 = 规则打标（白名单零分不入报 = 零噪音机制；比 LLM 稳，先满足
  ≥90% 准确——LLM 深度研判留给管线后续站）

## 实证

- 7/7 测试：双语文本打标 / 招标惩罚 / RSS 频道名剥除 / **零分过滤** /
  **网络全挂→缓存降级**（circuit_breaker 契约）/ Markdown 渲染分节
- 真实信源首跑：arXiv 可达源抓取成功；gov.cn 源不可达自动降级 exit 0
  （降级路径生产验证）；首跑抓到的频道名 bug 当场修复+回归钉死
- BET verify：exit 0（原 verify 命令 `-m bin.bc_os` 为连字符目录笔误，
  本 PR 修正为直跑路径）

## 07:30 呈递说明

本 BET 交付命令面（`policy_radar --generate-morning-brief` + `cockpit brief
--morning`）；定时调度（launchd 07:30 + 夜间抓取）属管线 T2-01 事件总线的
调度层接入，spec 已标注。
