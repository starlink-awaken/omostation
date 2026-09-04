---
schema_version: standard/v1
standard: incident-to-rule-pipeline
created: 2026-08-30
last_updated: 2026-08-30
owner: governance-team
adr: ADR-0443
---

# 事故→规则流水线（incident-to-rule pipeline）

> SSOT：本标准定义管道五步；机制载体是 `bin/gac/error-knowledge.py`（记录与晋升出口）
> 与 `.omo/_delivery/rule-drafts/`（草案区）。gate 报错即教学是实证最有效感知路径
> （scout 实证 2026-08-30），本管道把"事故→拦截→规则"闭环焊死。

## 五步契约

```
① 事故发生（gate 拦截 / 人发现踩坑）
   └─ ② pitfall 记录：error-knowledge.py record（fuzzy 症状去重，重复即 times_encountered++）
        └─ ③ 阈值：times_encountered ≥ 5（ESCALATION_THRESHOLD）
             └─ ④ 草案自动生成：.omo/_delivery/rule-drafts/CR-PITFALL-*.json
                （带 0431 契约字段：added_at / review_before=+90d / justification 引 pitfall 证据链）
                  └─ ⑤ 人审入册：审 draft_rule 的 executor/dimension 是否合理 →
                     lib/yaml_ssot_edit.py roundtrip 进 governance-checks.yaml（禁字符串手术）
```

## 硬约束

1. **草案不碰 registry**：`rule-drafts/` 只是等人审的 JSON；governance-checks.yaml 的
   写入永远走人审 + roundtrip 工具（HITL，ADR-0431 D4）。
2. **幂等**：同一 pitfall 只生成一次草案（文件存在即跳过）。
3. **证据链必带**：草案的 justification 必须引用 pitfall id + 遇到次数 + 首末确认日期，
   禁止无证据规则。
4. **review_before 继承 0431**：草案规则入册后 90 天复审——规则的死期在出生时写好。
5. **去重词阈值 ≥3**：record 的 fuzzy 匹配沿用既有语义（≥3 词命中视为同坑）。

## 反模式（禁止）

- 事故后直接手编 governance-checks.yaml（绕过 pitfall 记录 = 证据链断）
- 草案直接脚本合入 registry（无人审 = HITL 破防）
- 用 pitfall record 刷次数凑阈值（自报数据不作数——事件口径排除 self-data）

## 已固化样板例

- **PITFALL-SUB-001~003（submodule 未 init）**：拦截面为 `.githooks/pre-commit`
  submodule-guard，2026-08-30 已从硬编码 3 子模块扩为 `.gitmodules` 全量 14 个
  （ADR-0443 Q16）——类别级消灭，非个案修补。
