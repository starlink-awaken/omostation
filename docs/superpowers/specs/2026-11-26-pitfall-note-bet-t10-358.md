---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-358
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-26
accepted: "2026-11-26 Principal 会话「继续推进吧」— 对 T357 终报遗留项 (pitfall 立条 + note 订正) 的直接授权"
title: 管道吞 rc pitfall 追加 + mcptool reconciliation_note 订正
created: 2026-11-26
---

# BET-Y2Q4-T10-358: pitfall 追加 + note 订正 (T357 遗留收尾)

## 背景与问题

1. **管道吞 rc 两次自伤未立条**: `$?` 只反映管道末段是 POSIX 语义,
   `cmd | tail; echo $?` 拿的是 tail 的 rc。T356 实证形态 ① (traceback 后
   rc=0 假成功), T357 实证形态 ② (`&&` 链复合 —— merge 失败被 tail 吞,
   install 在旧 HEAD 跑出「已对齐」假象, 差点宣布假修复生效)。与既有
   zsh 条目的 PIPESTATUS 变体 (语法层) 不同根因 (语义层, bash/zsh 通杀),
   值得独立条目。
2. **mcptool note 声明面内部脱节**: T357 换链后 reconciliation_note 仍
   描述已消亡的 git add+commit 直提行为 (含 HEAD==main 守卫、';' 连接
   设计), note 与 command 互相矛盾。

## 方案

1. pitfalls.md 追加条目 (append-only 尾部): 证据 (T356/T357 两形态) →
   判据 (rc 采集点同段四法) → 纪律 (rc=0 但输出像失败先怀疑管道)。
   AGENTS.md §7 簇表「判据/检测器自身的可靠性」覆盖列同步短语。
2. mcptool note 订正: 断根行为置顶 (worktree+自动 PR, cmd_nonzero_ok
   承接 drift rc=1), 历史背景保留, PATH 语义标注由库内前置承接。

## 验收标准

1. `check-pitfalls-index.py` 无新红 (frontmatter last-reviewed bump 当日)。
2. registry.yaml 与 pitfalls.md YAML 解析通过。
3. 台账 606 bets + digest 绑定。

## 非目标

- 不动 zsh 条目原文 (PIPESTATUS 变体与本文互补不重复)。
- 不改 cron 命令链 / 脚本 (T356/T357 已断根, 直提家族清点确认零残留)。

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 追加独立条目 vs 并入 zsh 条目变体 | 独立条目 | 根因不同: POSIX 语义 vs zsh 语法; 交叉引用即可 |
| 2 | note 订正 vs 只留历史 | 断根置顶 + 历史保留 | note 须描述现行行为, 历史背景不删 |
