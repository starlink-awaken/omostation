---
schema_version: specification/v1
spec_version: 1.0.0
title: DLP quarantine sandbox & auto-sanitize
bet_id: BET-Y1Q4-T10-01
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-02
last_updated: 2026-09-02
type: ssot
last_updated: 2026-09-03
---

# DLP quarantine sandbox & auto-sanitize (T10-01)

## Intent

外发公文/邮件/外部模型调用前的本地防泄密闸：识别拦截涉密文号、身份证号、
手机号、机密财务预算、内部拓扑 IP，多级脱敏 + 高危强制挂起外发并报警
（"检测到机密文号，需夏明星二次确认"）。未脱敏原文绝不外传（non_goal 红线）。

## Architecture (KISS)

```
projects/ecos/src/ecos/governance/dlp_broker.py（规则引擎 + NER 插件接口）
├─ RULES: 涉密文号/密级标识/身份证18位/手机号/内部IP(10.|192.168.|172.16-31|100.64/10)/
│   财务预算(显式单位 alternation — Python re 可选链怪癖规避)
├─ scan(text) → findings[{type, span, risk, redaction}]
│   契约: <2ms (regex 热路径零模型), 识别率 100% (规则面, 评测集含对抗例)
├─ sanitize(text, level): partial(首尾保留)/mask/redact — 产物复扫零残留
├─ quarantine: high_risk → pending_approval + 中文报警 (TYPE_LABELS 单源)
│   永不自动外发
├─ NERBackend: 可选增强 (uer/roberta-cluener), 模型不在位快速跳过
└─ --test-dlp: 5 检查断言 (recall/误报/时延/挂起/脱敏闭环)

projects/cockpit/src/cockpit/commands/dlp_guard.py（命令面）
└─ cockpit dlp-guard --file/--text [--sanitize partial|mask|redact]
    Rich 报告 + exit 2 = 高危挂起 (人工确认语义)
```

## Verify (BET contract)

- `python -m ecos.governance.dlp_broker --test-dlp` → exit 0
- `make gac-local-gate` → exit 0
