---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: skill
name: bet-closeout-chain
title: BET Closeout Chain
description: "BET 完成闭环全链路 skill：从 spec binding 到 ledger complete 的 8 步 checklist（spec 规范/start 绑定/交付 PR/evidence matrix/complete/retro/closeout），固化 2026-09 两日 4 次（T10-02/T10-04/T7-02/T7-03）实战流程"
version: "1.0"
triggers: 
---


# bet-closeout-chain — BET 完成闭环 8 步

> 执行端是 `bin/plan/bet-ledger.py` + `bin/agent-workflow.py`；本 skill 是防考古 checklist。
> 违规症状对照：`SPEC_BINDING_REQUIRED` → 步 1-2；`missing_bet_binding` → 步 2；`missing_retro` → 步 6。

## 步 1 · Spec 落 canonical 位

- 路径：`docs/superpowers/specs/<date>-<slug>.md`（**必须**在此目录，别的路径 `SPEC_REF_INVALID`）
- frontmatter 七件套：`schema_version: specification/v1` / `spec_version: 1.0.0` / `title` / `bet_id: <BET-ID>` / `status: accepted` / `lifecycle: contract` / `last-reviewed: <date>`（缺 lifecycle/last-reviewed 会被 doc-governance 的 accepted-specifications surface 拦，valid_lifecycles=[spec,contract]）

## 步 2 · Ledger 绑定 + workflow start

- 台账条目加：
  ```yaml
  accepted_specifications:
  - spec_ref: repo://docs/superpowers/specs/<file>
    spec_version: 1.0.0
    content_digest: sha256:<file 的 sha256>
    decision_ref: decision://accepted/<BET-ID>
  ```
- digest = `shasum -a 256 <spec>`；**spec 内容再改必须重算**（COMPLETION_FILE_DIGEST_MISMATCH / SPEC_FRONTMATTER_VERSION_MISMATCH 的根源）
- `python3 bin/agent-workflow.py start project-doc-change --bet <BET-ID> --profile governance-agent`（缺 --bet 会被 requirement-iteration gate 拦）

## 步 3 · 交付 + 合并

- worktree claim → 改 → 显式列路径 `git add`（禁 add -A，见 PITFALL-COO-003）→ submit → CI 全绿 → squash 合并，记下 merge SHA

## 步 4 · Evidence matrix 入账

```yaml
completion_evidence:
  schema_version: completion-evidence-matrix/v1
  axes:
    engineering:
      status: VERIFIED            # 4 键缺一不可
      evidence:
        merged_reachable_commit: {ref: git://origin/main@<merge-sha>}
        tests:    {ref: receipt://<receipt>, sha256: sha256:<...>}
        diff:     {同上}
        rollback: {同上}
    operational:
      status: PROVEN              # 4 键: live_canary/fresh_receipt/replay/cleanup
      evidence: {...}
    value:
      status: NOT_PROVEN          # 治理类任务的默认
      evidence: {}
  overall_state: delivery_accepted
value_indicator_policy: false     # 不加则要求 value=ACCEPTED+真人签名 → OVERALL_STATE_MISMATCH
```
- receipt 通常 = `docs/reports/<date>-<slug>-closeout.md`；replay 指 retro 文件

## 步 5 · Retro

- `.omo/_knowledge/retros/<BET-ID>.md`，frontmatter 含 `bet_id: <BET-ID>`（chain 检查项）；四问结构（intended/happened/changed/lessons）

## 步 6 · Complete + Closeout

```bash
python3 bin/plan/bet-ledger.py complete <BET-ID>
python3 bin/agent-workflow.py closeout <run-id> --status ok --evidence "PR #N merged as <sha>; <验证摘要>" --from-diff
```
- closeout 常见拦：`missing_retro`（步 5 没落盘）；**verify 失败**（`closeout blocked: verify failed`）。
- verify 失败要**先分诊，不要靠重试 `--from-diff` 绕**——`--from-diff` 只改文件采集范围，不重算判定；
  且 `lifecycle.py` 里只有 `--status ok` 会被 verify 拦：
  1. `python3 bin/agent-workflow.py verify <run-id> --from-diff --execute` 取具体 `[FAIL] <check> :: <cmd>`；
  2. 判预存：`git diff --name-only origin/main...HEAD` 是否含该 check 读取的任何文件；再用
     `git show origin/main:<path>` / `git cat-file -s origin/main:<path>` 直接量 main 现状
     （不信本地工作树——共享主工作区的 HEAD 可能是别人的，PITFALL-COO-006）；
  3. 预存成立 → 用 `--status blocked` 收尾，把失败项**原文**、判据命令、"为何与本 diff 无关"写进
     `--evidence`。`blocked` 不是绕门禁，它把 `verify_ok=false` 如实入账；
  4. **禁止自签豁免**：known-debt 逃生口要求 `SWARM_ESCAPE_ID=local-preflight-preexisting && human_gate`
     且必须提交指纹（`harness-policy.yaml` § `known_debt.escape`），那是 principal 的权限。

## 步 7 · 收尾 PR + 清理

- evidence/retro 的 commit 走第二个 PR（squash 合并）→ `gac-worktree.sh release <session>`

## 常见坑速查

| 报错 | 缺哪步 |
|------|--------|
| COMPLETION_EVIDENCE_REQUIRED | 步 4 |
| SPEC_BINDING_REQUIRED | 步 1-2 |
| missing_bet_binding | 步 2（没 start） |
| BET_DONE_AT_REQUIRED | 台账缺 `done_at` |
| `closeout blocked: verify failed` | 步 6 分诊（先量预存，禁自签豁免；预存则 `--status blocked`） |
| vision→retro 链未闭合 | 步 2 + 步 5 |

## 相关

- `.omo/_knowledge/retros/BET-Y1Q4-T10-02.md` / `BET-Y1Q4-T10-04.md` / `BET-Y2Q1-T7-02.md` / `BET-Y2Q1-T7-03.md` — 4 次实战样例
- PITFALL-GAT-007 — CI 假失败分诊（push 前 rebase）
