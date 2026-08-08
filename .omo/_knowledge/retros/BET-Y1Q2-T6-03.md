# BET-Y1Q2-T6-03 Closeout: bin/ 孤儿脚本扫描与归档

**BET ID**: BET-Y1Q2-T6-03
**Track**: T6-SUBTRACT
**Window**: Y1Q2
**Status**: done
**Completed at**: 2026-08-08

## Objective
扫描 bin/ 目录下零引用孤儿脚本，归档以减少治理面。

## Analysis Method
对 bin/gac/, bin/delivery/, bin/collab/, bin/adr/, bin/ssot/ 下 50+ 脚本逐一检查 7 层引用面：
1. Makefile 直接调用
2. .githooks/ hook 引用
3. .github/workflows/ CI 引用
4. tests/ 测试引用
5. .omo/_truth/registry/ 注册引用
6. projects/ecos/.../GAC-RULE-*.yaml 规则引用
7. 跨脚本引用

## Confirmed Orphans (6 files, 0 references each)
| File | Directory | Notes |
|------|-----------|-------|
| backfill_bos_status.py | bin/gac/ | BOS status backfill, 一次性工具 |
| gac-execution-gap.py | bin/gac/ | 执行差距分析, 无 caller |
| x3-auto-distribute.py | bin/delivery/ | X3 自动分配, 无 caller |
| gac-branch-prune.sh | bin/gac/ | 分支清理, 被 gac-worktree.sh 取代 |
| state_sync.py | bin/delivery/ | 状态同步, 被 broker 路径取代 |
| m1-adversarial-probe.py | bin/gac/ | M1 探测, 一次性诊断工具 |

## Action
归档至 bin/_archive/t603-orphans/ (git mv, 保留历史可追溯)。

## Verification
- 6 个文件均通过 7 层引用检查确认为零引用
- 归档使用 git mv 保留 git history
- 不影响 make gac-local-gate 门禁 (无注册引用)
