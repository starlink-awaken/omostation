---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: standard/v1
standard: incident-to-rule-pipeline
created: 2026-08-30
adr: ADR-0443
---


# 事故→规则流水线（incident-to-rule pipeline）

> SSOT：本标准定义管道五步；机制载体是 `bin/gac/error-knowledge.py`（记录与晋升出口）
> 与 `.omo/_delivery/rule-drafts/`（草案区）。gate 报错即教学是实证最有效感知路径
> （scout 实证 2026-08-30），本管道把"事故→拦截→规则"闭环焊死。

## 五步契约

```
① 事故发生（gate 拦截 / 人发现踩坑）
   └─ ② pitfall 记录：error-knowledge.py record（fuzzy 症状只列候选；计数需显式 --confirm-dup）
        └─ ③ 阈值：times_encountered ≥ 5（ESCALATION_THRESHOLD）
             └─ ④ 草案生成：error-knowledge.py promote-drafts（幂等扫描，缺则补）
                  → .omo/_delivery/rule-drafts/CR-PITFALL-*.json（入仓，见下「队列耐久性」）
                （带 0431 契约字段：added_at / review_before=+90d / justification 引 pitfall 证据链）
                  └─ ⑤ 人审入册：审 draft_rule 的 executor/dimension 是否合理 →
                     lib/yaml_ssot_edit.py roundtrip 进 governance-checks.yaml（禁字符串手术）
                     → 删除对应草案 JSON（队列即等于待办；无 confirm/reject 子命令）
```

## 队列耐久性（BET-Y2Q3-T10-202，2026-09-24）

④⑤ 曾经是两个断头：晋升只挂在 `feed-escapes` 的内层循环和 `record --confirm-dup` 上，
而 escape 台账 `.omo/_delivery/swarm-escape/` 是 worktree-local 的；草案目录
`.omo/_delivery/rule-drafts/` 又落在 `.omo/_delivery/*` 忽略规则下。实测 2026-09-24：
37 个坑里 3 个已过阈值、队列里 0 份草案，`stats`/`check` 谁都不报这个缺口。因此：

- **队列入仓**：`.gitignore` 用 `!.omo/_delivery/rule-drafts/` 例外重纳，**并且**把该前缀加进
  `check-runtime-artifacts.py::WHITELIST_PREFIXES`（同步进 `ci-local-fast.py::run_runtime_artifact_gate()`
  那份同源实现）——入仓有两道锁，只解 `.gitignore` 会在 `git commit` 时被确定性地拦下。
  与 calibration/events/scene-outcomes 同一条先例：等人审的东西不能跟着 worktree 一起被回收。
- **回边独立**：`promote-drafts` 是只扫描已入库坑的晋升入口，不依赖本轮有没有 escape
  台账；`feed-escapes` 在缺台账时也照跑一次晋升扫描。
- **缺口可见**：`stats` 报 `overdue_rule_drafts`/`rule_drafts_stale_review`，`check` 增设
  只读 `rule_drafts` 段落。二者都**不改 `check` 退出码**——本 check 挂在 gac-local-gate 上，
  让「草案尚等人审」变红灯等于把 HITL 队列当成故障。
- **同类喂食**：喂食匹配与 ⑤ 的 record 匹配同守「限同类」——surface 未映射时按 `gate`
  归类，匹配也只在该类别内进行，跨类的 `times_encountered` 增加一律禁止。

## 硬约束

1. **草案不碰 registry**：`rule-drafts/` 只是等人审的 JSON；governance-checks.yaml 的
   写入永远走人审 + roundtrip 工具（HITL，ADR-0431 D4）。
2. **幂等**：同一 pitfall 只生成一次草案（文件存在即跳过）。
3. **证据链必带**：草案的 justification 必须引用 pitfall id + 遇到次数 + 首末确认日期，
   禁止无证据规则。
4. **review_before 继承 0431**：草案规则入册后 90 天复审——规则的死期在出生时写好。
5. **去重词阈值 ≥3 且限同类**：record 的 fuzzy 匹配（同 category + ≥3 词命中）只**列出候选**，
   不自动合并——默认按新坑入库，避免丢掉根因。只有 `record --confirm-dup <ID>` 才给该条目
   `times_encountered++`（候选外的 ID 直接报错）。阈值 5→草案晋升由这个计数驱动，
   自动合并等于让弱信号替人决定哪条规则该晋升（2026-09-24 实证两次误合并后才改）。

## 反模式（禁止）

- 事故后直接手编 governance-checks.yaml（绕过 pitfall 记录 = 证据链断）
- 草案直接脚本合入 registry（无人审 = HITL 破防）
- 用 pitfall record 刷次数凑阈值（自报数据不作数——事件口径排除 self-data）
- 手写草案 JSON（绕过 `_promote_rule_draft` = 证据链字段可与 pitfall 现值脱钩）
- 把 `confirm`/`reject` 当处置面：这两个子命令历史上只有解析器没有 handler（静默
  exit 0），现在显式 `NOT_IMPLEMENTED` 退 2。处置 = 入册后删草案。

## 已固化样板例

- **PITFALL-SUB-001~003（submodule 未 init）**：拦截面为 `.githooks/pre-commit`
  submodule-guard，2026-08-30 已从硬编码 3 子模块扩为 `.gitmodules` 全量 14 个
  （ADR-0443 Q16）——类别级消灭，非个案修补。
- **首批入仓队列（2026-09-24 由 `promote-drafts` 补齐，待人审）**：
  `CR-PITFALL-COO-003`、`CR-PITFALL-GAT-004`、`CR-PITFALL-GAT-005`。其中
  `CR-PITFALL-GAT-004` 的证据链本身就是反面教材——它引用的 symptom 是一段
  `[PASS]` 日志摘录、标题写着 `(8x)` 而计数已到 46、`last_confirmed` 停在
  2026-08-30。审它的人必须先判定「这条坑到底还被不被确认」，而不是照计数放行。
