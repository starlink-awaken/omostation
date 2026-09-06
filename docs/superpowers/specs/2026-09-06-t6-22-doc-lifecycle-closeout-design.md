---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T6-22
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T6-22 文档生命周期收口 — 增量补齐与重复指针化设计

## 1. 目标

T6-22 主体（doc-lifecycle.py 三模式、主仓 frontmatter 清零）已由
前置交付完成。本 spec 收口剩余增量：BRIEF.md 补 frontmatter、
2 组重复 GOVERNANCE.md 的合并指针化，达成 done_when 全项。

## 2. In scope

1. `BRIEF.md`：补规范 frontmatter（type: ephemeral/generated,
   owner, source 指向 system.yaml, last_updated）。
2. 重复组 1（metaos/l4-kernel/model-driven/observability/runtime/
   aetherforge 六仓 GOVERNANCE.md 同内容）：主模板保留一处为 SSOT
   （projects/ecos 的 governance 规范或既有 standards 引用），其余
   五仓改为指针化 stub（frontmatter + 指向 SSOT 的链接 + 一行说明）。
   注：子仓文档改动随各子仓 main 提交。
3. 重复组 2（cockpit/ecos GOVERNANCE.md 内容近同）：同上指针化。
4. `docs/reports/doc-ssot-inventory-2026-09-05.md`：补充收口记录节。
5. 完成后 `doc-lifecycle audit` 重复组清零、lint 0 错误、
   `doc-ssot-lint` 与 freshness gate 维持绿。

## 3. Out of scope

- 不改 doc-lifecycle.py 本体（已交付）。
- 不动 Documents 域（另一治理平面）。

## 4. 验收（对齐 ledger done_when）

1. doc-lifecycle.py 三模式可用（前置已交付，本 spec 复验）。
2. 主仓无 frontmatter 文档数 0（BRIEF.md 补齐后）。
3. 2 组重复文档完成合并指针化（audit 重复组清零或降为合理引用）。
4. doc-ssot-lint / freshness gate 0 错误。
