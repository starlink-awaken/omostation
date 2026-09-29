---
schema: md/v1
schema_version: specification/v1
spec_version: 1.1.0
title: "Worktree release-diagnose 精确分类"
bet_id: BET-Y2Q4-T10-211
status: accepted
lifecycle: contract
owner: governance-agent
last-reviewed: 2026-09-28
---

# Problem

`release-diagnose` 已提供只读残留检查，但当前 root 状态分类仍部分依赖路径猜测：`projects/*` 会被统一标成 pointer，即使它只是普通根文件；同时缺少 gitlink、生成物、PASW 孤儿目录和特殊路径的边界覆盖。误分类会让 release 前置诊断给出错误修复建议。

# Goal

在不改变 `release` 行为、默认文本输出和 `0/1/2` 退出码的前提下，使 `release-diagnose` 基于 Git 元数据和现有 PASW 规则提供稳定、可解释的残留分类。

# Non-goals

- 不接入或改变 `release` 的清理门禁。
- 不新增 JSON 输出契约。
- 不执行 reset、stash、clean、remove、delete、checkout 或任何修复写操作。
- 不读取文件内容做语义判断。
- 不重构既有 worktree 生命周期流程。

# Design

## Root status classification

对 root `git status --porcelain` 中的每个路径，使用 index mode 判断是否为真实 gitlink：

- mode `160000`：`[gitlink]`，建议 `review-pointer`；
- `.omo/*`、`docs/generated/*`、`docs/cli/*`：`[generated]`，建议 `review-generated`；
- 其他路径：`[dirty-root]`，建议 `preserve-and-review`。

不再使用 `projects/*` 作为 pointer 的充分条件。gitlink 的分类来自 Git index 元数据，不来自目录名。

Root 状态解析必须保留现有文本输出兼容性，并正确处理 staged、unstaged、untracked 以及包含空格的路径。rename 状态至少不得把旧路径误报成新的独立残留。

## Submodule classification

普通子模块继续通过递归 `git submodule foreach` 枚举。子模块内部存在改动时输出 `[dirty-submodule]`，建议 `preserve-and-review`。root 层 gitlink 状态与子模块内部工作树状态允许同时出现，但必须分别表达 pointer 变化和内容变化，不能把子模块内部内容误报为普通 root 文件。

## PASW classification

- 配置的 PASW 路径存在但不是可识别 Git worktree：`[invalid-pasw]`，建议 `remove-stale-metadata`；
- `.subtrees/*` 下存在目录但不属于配置的 PASW 集合：`[orphan-pasw]`，建议 `preserve-and-review`；
- 可识别且干净的 PASW 不产生 finding。

PASW 检查只读访问 worktree 元数据，不尝试修复或删除目录。

## Exit contract

- `0`：所有可检查对象干净；
- `1`：检查成功但至少存在一个 finding；
- `2`：session/worktree、子模块或必要元数据不可读取。

## Compatibility

- 默认文本输出保持现有前缀和 recommendation 字段形式；新增分类只扩展类别，不改变成功/发现/不可读的退出语义。
- `release` case 和其他 `gac-worktree.sh` 命令不变。

# Testing

扩展 `tests/test_gac_worktree_release_diagnose.sh`，覆盖：

1. 普通 dirty root；
2. 真实 gitlink/pointer 变化；
3. dirty submodule；
4. generated path；
5. 配置 PASW 元数据损坏；
6. 未配置 PASW 孤儿目录；
7. 含空格路径和 rename 状态；
8. 诊断前后文件内容、`git status` 和目录结构保持不变。

保留已有 clean、missing session 和生命周期测试作为回归验证。

# Verification

- shell syntax check；
- release-diagnose focused test；
- existing worktree lifecycle tests；
- affected-graph/agent-workflow verification；
- repository governance gate and CI checks。
