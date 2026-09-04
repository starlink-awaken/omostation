---
schema_version: specification/v1
spec_version: 1.0.0
title: Policy radar & morning brief
bet_id: BET-Y1Q4-T7-03
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
type: ssot
last_updated: 2026-09-03
---

# Policy radar & morning brief (T7-03)

## Intent

7x24 巡检卫健委/医保局/工信部政策公告 + arXiv/bioRxiv 数字医疗文献，夜间提炼，
每日 07:30 晨报呈递 Cockpit。数字大脑 P0 管线首站。

## Sources (whitelist, no self-media)

- 政策: 卫健委 nhc.gov.cn 政策公告 / 医保局 nhsa.gov.cn / 工信部 miit.gov.cn
- 文献: arXiv (heal-ph / cs.AI 医疗交叉) / bioRxiv (medRxiv 镜像源)

## Architecture (KISS, two-day appetite)

```
bin/bc-os/policy_radar.py（引擎，标准库零依赖）
├─ fetch: urllib + per-source timeout 15s；失败→缓存快照降级（circuit_breaker 契约）
├─ 研判 v1 = 规则打标（白名单关键词→业务标签）+ 价值评分（标题权重）
│   标签: 医疗大模型 / 数据要素 / 互联互通 / 政务数字化 / 医保支付 / 其他政策 / 文献前沿
│   （LLM 研判留管线后续站——规则比 LLM 稳，先满足"零噪音+≥90%"）
├─ 产物: .omo/state/policy-radar/cache.json（降级快照）+ brief-YYYYMMDD.json + Markdown
└─ CLI: --generate-morning-brief（verify 契约，exit 0）

projects/cockpit/src/cockpit/commands/brief.py（扩展）
└─ `cockpit brief morning` 子命令：读当日 JSON → Rich 面板渲染（原会话简报保持默认）
```

## Scoring & noise control

- 白名单关键词命中才入报（未命中→other 桶不呈递）
- 政策源标题含机构关键词（通知/公告/意见/方案）加分；文献源标题含方法/数据集词加分
- 每源 top-N（3）+ 总量上限（15 条）——晨报是摘要不是信息流

## Degradation (circuit_breaker)

网络异常 → 读 cache.json（最近成功快照）生成降级版晨报（标注"缓存快照"），exit 0。
无缓存 → 空晨报 + 明确提示，exit 0（不阻塞）。

## Acceptance mapping (BET done_when)

- 07:30 呈递: `cockpit brief morning` 渲染当日 JSON（调度层后续站接 launchd，本 BET 交付命令面）
- 业务打标: 规则标签覆盖 done_when 列举条目（医疗大模型/数据要素互联互通）
- 零噪音 ≥90%: 白名单机制 + fixture 回归测试（打标准确率断言）
