---
schema: md/v1
schema_version: specification/v1
spec_version: 1.0.0
title: "Worktree release-diagnose 只读残留诊断"
bet_id: BET-Y2Q4-T10-211
status: accepted
lifecycle: contract
owner: governance-agent
last-reviewed: 2026-09-28
---

# Problem

`gac-worktree.sh release` 只有成功释放或拒绝释放两种结果。遇到 dirty root、dirty submodule、失效 PASW 元数据或派生文件漂移时，操作者必须手工拆解状态，容易误删或重复检查。

# Goal

新增只读命令 `release-diagnose <session>`，在不修改工作树的前提下分类释放阻塞项并给出下一步建议。

# Design

- 修改 `bin/gac/gac-worktree.sh`，新增 `release-diagnose` 分支。
- 复用 release 使用的 session 路径、普通子模块枚举和 PASW 配置；不得复制一套独立的 worktree 发现规则。
- 输出四类检查：root、普通子模块、PASW 子树、未跟踪文件。
- 分类规则只基于路径/元数据，不读取内容并做语义推断：
  - `.omo/**`、`docs/generated/**`、`docs/cli/**`：`review-generated`
  - gitlink 变化：`review-pointer`
  - 无法被 Git 识别的 `.subtrees/<name>`：`remove-stale-metadata`
  - 其他 tracked/untracked 源文件：`preserve-and-review`
- 退出码：0=无阻塞项；1=诊断成功但发现阻塞项；2=无法读取 session 或元数据。
- 命令绝不执行 reset、stash、clean、worktree remove、branch delete 或文件写入。

# Verification

- shell 测试覆盖 clean worktree、dirty root、dirty submodule、invalid PASW metadata。
- 现有 release 路径行为保持不变。
- `bash bin/gac/gac-worktree.sh release-diagnose <session>` 在真实 session 上只读运行。
