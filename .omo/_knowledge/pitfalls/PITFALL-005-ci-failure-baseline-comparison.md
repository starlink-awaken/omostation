---
id: PITFALL-005
status: active
lifecycle: pattern
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
type: ssot
---

# PITFALL-005: CI Failure Baseline Comparison (CI 失败先做基线对比)

> **2026-09-17 沉淀** · 来源: PR#3843 cascading_test 2 个失败（test_favicon / test_unknown_path）实证
> 适用: 任何 PR 出现 CI 失败, 尤其是 cascading_test / doc-index / lint 类检查

## TL;DR

CI 红了不等于你搞砸了。多 agent 共享主树环境下, **CI 失败经常是 pre-existing**（main 上本来就有的问题）。看到红色先做基线对比, 确认是你引入的再动手修。

## 诊断三步法

1. **看 PR diff 文件清单**: 失败文件在不在你的变更里? 不在 → pre-existing
2. **git stash 跑基线**: `git stash && git checkout origin/main && <跑失败测试> && git checkout - && git stash pop`
3. **查近 5-10 个 PR**: 同检查是不是都在 fail → pre-existing

## 陷阱表

| 陷阱 | 症状 | 对策 |
|------|------|------|
| 看到红色就改自己代码 | 改了半天发现 fail 文件在子模块里, 跟你的改动无关 | 先看 diff 文件清单, 排除 gitlink 后是否还触发 |
| cascading_test 失败 | 子模块 pre-existing 问题被你的 PR 连带触发 | 确认 fail 文件归属, 子模块问题留给子模块 owner |
| doc-index 失败 | CI 浅克隆不拉子模块, 文件数跟本地不同 | 本地全量 checkout 0 hard failures ≠ CI 1 hard failure |

## 实证

PR#3843 (ADR-0437→0439 引用修复):
- cascading_test 报 test_favicon_returns_404 / test_unknown_path_returns_404 失败
- git stash 后在 origin/main 上跑同样测试 → 同样失败
- 结论: pre-existing, 跟本次改动无关, 合并 PR

## 与 PITFALL-COO-004 的关系

PITFALL-COO-004 聚焦 **lint fail** 的子模块归属判定。
PITFALL-005 聚焦 **任意 CI 失败** 的通用基线对比方法论。
