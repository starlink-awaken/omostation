---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-03
last-reviewed: 2026-09-03
bet: BET-Y1Q4-T3-03
title: 三层投机路由
symptom: squash 语义修复两次被并行覆盖 (commit 从未落库); 工作树材料被 checkout 挤掉
solution: 专属文件立即 commit + git show --stat 验证锁定; stash 恢复链
type: ephemeral
status: archived
---

# BET-Y1Q4-T3-03 复盘

## 做对了什么

1. **DRY 扩展**: 不重写 ADR-0197 SpeculativeRouter — 三层 TieredRouter 组合其语义;
   gateway 侧语义镜像不 import omlxc。
2. **规则热路径**: 路由决策纯规则, 实测 0.0045ms (契约 220 倍余量), 无抖动结构性保证。
3. **投机级联**: draft 始于 light + 置信 <0.7 升阶; slots 复用 T2-02 意图分类规则面。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| squash 语义修复两次"消失" (commit ok 但 -S 搜索空 — add/commit 竞态) | 第三次: 专属路径 add + 立即 git show --stat 锁定 |
| 未提交材料被并行 checkout 挤掉 (retro/spec 丢) | stash@{1} 恢复 ledger; 文件重写; 一次 commit 锁死 |

## 治理沉淀

**"commit 成功"必须验证内容**: 共享 worktree 竞态下 add 与 commit 之间工作树可变,
关键修复后 `git show HEAD --stat | grep <file>` 是肌肉记忆。
**未提交材料随时可丢**: 写完即 commit (小步提交), 不留未保存窗口。

## 后续

- light 层接真实 1.5B/3B provider (接口位已留)
- gateway route_request 接 rpc 面真实流量
