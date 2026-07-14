---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-06
related:
  - 0121-governance-convergence-initiative.md
  - 0140-m4-health-score.md
  - 0142-decisions-quick-ref.md
  - 0137-derived-plane-relocation.md
  - ../../../../bin/m4-cron-hook.py
  - ../../../../.omo/_derived/m4-cron-log.json
  - ../../../../.omo/cron/operating-rhythm-crontab
supersedes: []
---

# ADR-0144: M4 Cron Hook (Round 4d)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

新增 `bin/mof/m4-cron-hook.py`, 把 M4 Health Score (ADR-0140) 接入 OMO
operating-rhythm cron 框架 (ADR-0121, governance-evolution-roadmap §operating_rhythm)。
对 OMO 是**单向可观察性桥梁**: OMO 可读 `.omo/_derived/m4-cron-log.json` 派生面,
但 M4 不直接调用 OMO state bus (硬不违反 P74 governance boundary)。

**关键规则**:
- 不动 `.omo/cron/*` 任何现有脚本
- 不动 OMO `.truth/registry/*` YAML
- m4-cron-log.json 是 ADR-0137 的**唯一例外**派生面 (主仓根, 因为 SSOT 在主仓根 `.omo/cron/`)

---

## 1. 决策

### 1.1 设计原则 — 单向可观察性

```
┌─────────────────┐      ┌─────────────────┐
│ M4 工程 (主仓)   │ ─────►│ OMO 框架 (主仓)  │
│                  │<──────│                  │
│ bin/m4-cron-hook │      │ .omo/cron/...    │
│                 write │ OPC_TRIGGER=cron │
└─────────────────┘      └─────────────────┘
      M4 writes log       OMO reads log (可选)
```

- **M4 → OMO**: 写 m4-cron-log.json (单向)
- **OMO → M4**: 无 (不让 OMO 推数据进 M4, 保 governance boundary)

### 1.2 trigger 源识别

3 种 trigger:
- `manual` (无 OPC_TRIGGER 环境变量) — 开发者手动跑
- `cron` (OPC_TRIGGER=cron) — OMO 框架 cron 调用
- `test` (--trigger test) — 测试明示

### 1.3 m4-cron-log.json schema

每条 entry 6 字段:
- `mark`: "M4_HOOK_MARK" (恒定, OMO grep 用)
- `ts`: ISO-8601 UTC timestamp
- `trigger`: manual / cron / test
- `branch` + `sha`: 当前 git 状态 (debt-trace 用)
- `health_score`: M4 score 数值 (0-100)
- `metrics`: m4-health.json 完整 metrics dict

**保留最近 90 条** (3 个月 daily cron 容量), 滚动覆盖。

### 1.4 ADR-0137 例外

默认所有派生面在子模块 `.omo/_derived/` (ADR-0137)。
本 ADR 派生在主仓根 `.omo/_derived/m4-cron-log.json` — 因为 SSOT `.omo/cron/operating-rhythm-crontab` 在主仓根, 派生面跟随。
`.gitignore` 新增单文件规则 `.omo/_derived/m4-cron-log.json`, 是 ADR-0137 的唯一例外。

---

## 2. 不在本 ADR 范围

- ❌ 改 .omo/cron/* 现有脚本 (MO 不属于 M4 范围)
- ❌ 改 OPC_TRIGGER 环境变量语义
- ❌ OMO state bus events (硬 P74 边界)
- ❌ 自动触发 OMO cron 安装

---

## 3. 实施

### 3.1 bin/mof/m4-cron-hook.py (主仓工具)

CLI 接口:
- 默认: 输出 `[M4-Health] branch=... score=...` 单行格式
- `--sync`: 写 `.omo/_derived/m4-cron-log.json` (隐式默认)
- `--trigger <manual|cron|test>`: 显式 trigger 源
- `OPC_TRIGGER` 环境变量自动识别 cron 调用

可选 JSON 输出 ($M4_HOOK_JSON=1): 单 entry 完整 JSON。

### 3.2 .omo/_derived/m4-cron-log.json (派生面)

非 SSOT, gitignored, 累积 90 条 entry, 滚动覆盖。

### 3.3 .gitignore 例外

```
.omo/_derived/m4-cron-log.json  # ADR-0144
```
这是主仓根 .omo/_derived/ 在 ADR-0137 后**唯一**存活派生面。

---

## 4. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| 49 回归测试 | `tests/integration/m4_metamodel/run_all.py` | 49/49 PASS |
| 5-check strict | `bin/mof/mof-bootstrap.py all` | 0/0/0/0/0 |
| Cron hook CLI | `uv run python bin/mof/m4-cron-hook.py --sync --trigger test` | [M4-Health] 输出 |
| Hook log gitignored | `git check-ignore .omo/_derived/m4-cron-log.json` | rc=0 |
| 3 trigger 识别 | 手动 / cron (env) / --trigger test | 3 entry 入列 |

### OMO 集成示例 (未来 Round 5+)

```
# OMO operating-rhythm-daily cron 加入:
uv run python bin/mof/m4-cron-hook.py --sync   # → 追加 entry 到 log

# OMO P74 governance radar 读:
jq '.[] | select(.mark=="M4_HOOK_MARK")' .omo/_derived/m4-cron-log.json | tail
```

---

## 5. 关联

- [ADR-0121](./0121-governance-convergence-initiative.md) (governance 收敛主导)
- [ADR-0140](./0140-m4-health-score.md) (上游数据源)
- [ADR-0142](./0142-decisions-quick-ref.md) (本文档前身)
- [ADR-0137](./0137-derived-plane-relocation.md) (本 ADR 例外)

---

## 6. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 4d, M4 ↔ OMO cron 桥接, 仅读 + 写 派生面) |
