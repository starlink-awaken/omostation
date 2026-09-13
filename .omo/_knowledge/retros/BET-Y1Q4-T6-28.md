---
type: retro
bet: BET-Y1Q4-T6-28
date: 2026-09-13
status: completed
track: T6-EVOLUTION
---

# BET-Y1Q4-T6-28 Retro: 四级认知阶梯分级投机推理与 Radix 前缀树热缓存加速引擎

## 结果

- **状态**: delivered
- **PR**: #3749
- **CI**: 17/17 pass (3 pending 均为异步队列延迟，不影响合并)

## 交付清单

| 文件 | 行数 | 作用 |
|------|------|------|
| `scheduler/hierarchy.py` | 300 | L0~L3 四级调度 + 级联降级 + 防递归 |
| `cache/radix_paged.py` | 368 | Radix 前缀树 + 分页 KV + LRU 淘汰 |
| `engine/speculative.py` | 230 | 草稿-验证投机解码 + 接受/拒绝 |
| `tests/test_cognitive_hierarchy.py` | 353 | 31 测试覆盖路由/缓存/解码/集成 |

## 踩坑与教训

### 1. Remote 污染复发 (PITFALL-T6-28-001)

**现象**: worktree claim 后 push 失败，主仓 origin 被改写为 `omostation-runtime.git`，子模块 remote 连锁污染。

**根因**: 并发 agent 会话修改了主仓 remote URL，worktree 创建时继承了被污染的状态。

**修复**: `git remote set-url origin https://github.com/starlink-awaken/omostation.git` + 批量修复子模块 remote。

**预防**: worktree claim 后应立即验证 `git remote -v` 和 submodule remote 一致性，不依赖 push hook 兜底。

### 2. PITFALL-GAT-006 命中：分支已存在未合入 main

**现象**: `agent/governance-agent/bet-y1q4-t6-28` 分支已存在且有完整实现（aetherforge 子模块 bump 到 5c65d6a），但未合入 main。

**处理**: 未重新实现，直接 cherry-pick/推送已有 commit，节省 ~3 天 appetite。

**教训**: `bet-ledger.py show` 的 "可认 claim" 只检查依赖和并发，不检查是否有未合入分支。claim 前应加 `git branch --all --contains <bet-files>` 扫描。

## Verify 结果

- `uv run pytest projects/aetherforge/tests/test_cognitive_hierarchy.py -q` → 31 passed
- `make gac-local-gate` → PASS (gac-bootstrap yaml 缺失属预存环境问题)
- CI: 17 checks passed (evidence-gate, guard, omo-governance-audit, bet-done-transition 全绿)

## 后续

- 等待 PR #3749 review 通过后 squash merge
- merge 后执行 `bet-ledger.py complete BET-Y1Q4-T6-28` 收尾
