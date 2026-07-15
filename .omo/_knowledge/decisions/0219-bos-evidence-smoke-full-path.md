---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
related:
  - 0216-compass-feedback-partial-smoke.md
  - 0217-workflow-hygiene-layer-check-and-evidence.md
supersedes: []
---

# ADR-0219 — BOS 全量 evidence-smoke 可复现路径

- **Status**: ACCEPTED
- **Date**: 2026-07-15

## Context

ADR-0216 允许 agora import 失败时 **partial** smoke（仅 feedback）。全量 BOS
（`POC_SERVICES` resolve 率）仍需 `projects/agora` + pydantic/fastmcp。实测：

| 环境 | 结果 |
|------|------|
| 根 python3 无 agora .venv | partial / import_failed |
| `cd projects/agora && uv sync` 后根 python3 | **full**: resolve≈0.987, gap=0, score≈99.2 |
| agora pin 含 `pydantic>=2.0` (#401) | 依赖可解析 |

## Decision

### D1 — evidence-smoke 自动 bootstrap

import 失败时执行一次 `uv sync` in `projects/agora` 并注入 `.venv` site-packages，再试 import。
仍失败才 partial。

### D2 — `make evidence-smoke`

一键入口：确保 submodule 存在后跑 JSON smoke 并打印 score/resolve/gap。

### D3 — 成功判据

- `partial` 缺省/false
- `bos.gap == 0`（deprecated 可 >0）
- `bos.resolve_rate >= 0.95`
- `feedback_loop.alive == true`

## Evidence (2026-07-15)

```
score=99.2 partial=None resolve=0.987 gap=0 feedback=True
declaration_count=154 resolvable=152 deprecated=2
```
