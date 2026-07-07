---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0162-p76-phase8-real-engineering.md
  - 0161-p76-phase7-llm-cron-tasks-mesh.md
  - ../../../../../.githooks/prepare-commit-msg-commit-assist
  - ../../../../../bin/commit-assist.py
supersedes: []
---

# ADR-0163: P76 Phase 9A — commit-assist pre-commit-msg 集成 (advisory 硬门)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P76 Phase 7 (LLM-assisted commit) 的"默认启用"实现步骤。

## 0. TL;DR

Phase 7 留下 follow-up: "commit-assist default-on (commit-assist 自动 pre-commit)". Phase 9A 治本:
- 新增 `.githooks/prepare-commit-msg-commit-assist` (advisory hook)
- 修改 `Makefile::install-hooks` 安装新 hook
- 更新 `.githooks/README.md` 文档

## 1. 设计 (WHY/WHAT/NEXT)

### 1.1 WHY

Phase 7 ADR-0161 沉淀原则 P76-7-1: **llm-advisory-not-autonomous**. 当前 `bin/commit-assist.py` 是手工工具 — developer 需要主动跑. 

集成到 git workflow 后, every `git commit` 自动获得 suggestion, 但**硬门**: LLM 不能直接写 commit msg. developer 必须 `git commit -F .commit-suggestion` 显式接受.

### 1.2 WHAT — advisory hook

`.githooks/prepare-commit-msg-commit-assist`:

```bash
# Trigger条件:
#   git commit (无 -m) → 调 EDITOR, prepare hook 注入 msg
#   git commit -m "..." → COMMIT_SOURCE=message, 跳过
#   git commit -F <file> → COMMIT_SOURCE=message, 跳过
#   amend / merge / squash → template mode, 跳过

# 行为:
#   1. 检测 staged 改动 (空 → exit 0)
#   2. 调 bin/commit-assist.py --no-llm (heuristic fallback, P76-7-2)
#   3. 写侧车 .commit-suggestion (gitignored)
#   4. 在 commit msg file 末尾追加 hint 行 (developer 看到 → 可选择 -F .commit-suggestion)
#   5. exit 0 (永不断 commit, P76-7-5 fail-safe)
```

### 1.3 WHAT — install 集成

`Makefile::install-hooks`:
- 复制 `prepare-commit-msg-commit-assist` 到 `.git/hooks/`
- 输出 "✅ 已装 LLM advisory hook (P76 Phase 9A)"

### 1.4 跳过模式 (developer 显式意图)

| 模式 | COMMIT_SOURCE | 行为 |
|------|---------------|------|
| `git commit` | (空) | hook 跑 |
| `git commit -m "msg"` | `message` | 跳过 |
| `git commit -F file` | `message` | 跳过 |
| merge / squash | `template` | 跳过 |
| amend | `commit` | 跳过 |

## 2. 沉淀原则 (P76-9A)

| # | 原则 | 含义 |
|---|------|------|
| P76-9A-1 | **git-native-trigger** | 不用 polling / daemon, 用 git 已有 hooks 机制 |
| P76-9A-2 | **sidecar-not-injection** | suggestion 写侧车, 不直接修改 commit msg (P76-7-1 advisory) |
| P76-9A-3 | **fail-silent-not-fail-block** | hook 失败 → 不阻 commit. 网慢/LLM 不可达 → 用 heuristic |
| P76-9A-4 | **heuristic-default** | 本地调 `--no-llm` 不依赖 aetherforge/ollama 服务可用 |
| P76-9A-5 | **respect-developer-intent** | -m / -F / amend / merge 全部跳过 (developer 已选 source) |

## 3. 不在本 ADR 范围

- ❌ commit-assist 默认 aetherforge 网关 / 上 `3-tier LLM` (--no-llm 只用 heuristic)
- ❌ 写在 pre-commit (我们写 prepare-commit-msg — 更早触发, 不影响 staged-content 守门)
- ❌ 强制接受 (developer 仍可拒绝, hook 只是 advisory)

## 4. 验证清单

- [x] `.githooks/prepare-commit-msg-commit-assist` 创建
- [x] Makefile::install-hooks 集成新 hook
- [x] `.githooks/README.md` 文档
- [x] 实测: hook 跑 → .commit-suggestion 写入 → commit msg file 追加 hint → exit 0

## 5. 关联

- ADR-0161 (Phase 7 commit-assist 创建)
- ADR-0159 (Phase 5 foundry 雏形)
- ADR-0140 / 0141 (CR-X1-GOD-MODULE-LIMIT 守门)
- doc/operations/knowledge-foundry-monitor.md (cockpit 面板)
- bin/commit-assist.py (Phase 7 主交付)

---

*最后更新: 2026-07-07 · P76 Phase 9A 治理闭环 + commit-assist default-on · ACCEPTED*
