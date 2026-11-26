---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-357
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-26
accepted: "2026-11-26 Principal 会话「go」— 对 T356 终报中「同族第二例 mcptool 直提断根 + 装重缺陷处置」的直接授权"
title: mcptool-impl-drift 直提断根 (共享库提炼) + install-cron-plane 装重缺陷修复
created: 2026-11-26
---

# BET-Y2Q4-T10-357: mcptool 直提断根 + 装重修复

## 背景与问题

1. **同族第二例**: `check-mcptool-impl-drift` job (.omo/cron/registry.yaml:1028,
   每日 05:45) 与 T356 断掉的 capability-sync 同款主仓直提链
   (`git add && git commit`), 多一层 HEAD==main 防御但 push 失败照样滞留分叉。
2. **装重缺陷** (T356 收尾实测): `install-cron-plane --install` 声称
   「去掉登记面里内容不同的旧行」, 实际没做到 —— `comparison_key` 是归一化
   整行, 命令链一改版 (旧直提链 → 新 --publish 链) 旧行键对新不上, 被当
   外部工具行保留 → 新旧两条并存, 旧链照跑, 断根失效。T356 收尾靠手工清理。

## 方案

### 1. 共享库提炼 `bin/lib/cron_pr_publish.py`

从 gen-capability-registry.py 抽出 `publish_via_pr()` (T356 已 merge 的实现),
参数化: `workspace / run_cmd / add_paths / branch_prefix / title / body /
cmd_nonzero_ok`。生成器 `--publish` 改薄壳调用 (行为不变)。分支名
`{branch_prefix}-YYYYMMDD`, 其余流程 (fetch → worktree+子模块 → 跑命令 →
无漂移即弃 → commit/push → gh pr create + merge --squash --auto → 清理)
与 T356 一字不差。

### 2. mcptool 加 `--publish` (`bin/ssot/check-mcptool-impl-drift.py`)

同款薄壳, `cmd_nonzero_ok=True`: drift 存在时 `--report` rc=1 是业务信号
(report 已写出), 不是执行失败。worktree 内跑 `--report`, add
`.omo/_truth/registry/mcptool-drift-report.yaml`。

### 3. registry.yaml:1028 换链

`cd "$HOME/Workspace" && /opt/homebrew/bin/python3.13
bin/ssst/check-mcptool-impl-drift.py --publish >> runtime/cron/mcptool-drift-report.log 2>&1`
(旧 HEAD==main 防御在 worktree 模式下天然不需要 —— 基点就是 origin/main)。

### 4. 装重修复 (`bin/lib/cron_normalize.py` + `bin/ops/install-cron-plane.py`)

- `cron_normalize.py` 加 `script_signature(line)`: schedule 五域 + 行内第一个
  `bin/**.(py|sh|ts)` 路径组成签名。
- `_is_managed` 判据扩: 键相等 **或** 签名相等 ⇒ 登记面行 (替换)。
  命令链改版后的旧行从此可被认领; 外部行引用本仓脚本路径的概率可忽略。

## 验收标准

1. `ast.parse` 两脚本通过; `gen-capability-registry.py --publish` 回归
   (无漂移路径 rc=0, 行为与 T356 一致)。
2. mcptool `--publish` 端到端真跑: 干净 worktree 生成 report → 无漂移跳过
   rc=0 / 有漂移 → PR 创建 + squash --auto。
3. 装重重演: 在 crontab 造一条旧形态直提行 → `--install` → 旧行被替换,
   无并存。
4. 台账 605 bets + digest 绑定; gac-local-gate 除 ratio (waiver) 外全绿。

## 非目标

- 不迁移其余 cron job (直提家族全量清点另立 BET——本 BET 只修已知两例)。
- 不改 gen-help-docs / post-commit-sync-check 职责边界。
- 不动 ADR-0373 sentinel。

## 风险与回退

- mcptool drift report 若真有漂移 → 真 PR (预期内, 顺手同步真值面)。
- 签名匹配误删外部行: 外部行引用本仓 bin/ 脚本 + 同 schedule 才命中,
  概率可忽略; crontab 变更有备份 (本 BET 前 T356 的备份仍在)。
- 回退: revert 本 PR。

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | mcptool --publish 复制 110 行 vs 提炼共享库 | 共享库 | DRY; 两 job 已是同族, 第三个直提 job 出现时零成本接入 |
| 2 | 装重缺陷修 vs 立债 | 顺手修 | ~20 行; 不修则 T357 收尾重装必再犯 (T356 手工清的教训) |
| 3 | drift rc=1 语义 | cmd_nonzero_ok | report 已写出即执行成功; drift 是业务信号 |
