---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-06
related:
  - 0150-submodule-pr-reverse-review.md
  - 0149-p71-baseline-no-replay.md
  - 0141-m2-base-schema.md
  - ../../../../bin/check-submodule-hygiene.py
  - ../../../../.gitignore
  - ../../../runtime/.gitignore
supersedes: []
---

# ADR-0151: 子模块 gitignore 守门 (Round 5f)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

新增 `bin/ssot/check-submodule-hygiene.py` 工具,持续验证 3 类子模块卫生问题:
1. **submodule-dirty**: 任意子模块内部有 uncommitted changes (本地子模块脏)
2. **tracked-derived**: 派生面路径被 tracked (应是 gitignored, ADR-0129 派生面范式)
3. **submodule-pointer-stale**: 任意子模块 SHA 与 origin/main 不一致 (PR 推动会 reset)

**实证捕获**:
- `runtime/.watch-dispatch-stamps.json` 应 gitignored, 但已 tracked — 治本
- 主仓 `.gitignore` 加 `runtime/.watch-dispatch-stamps.json` 规则 + `git rm --cached` untrack

---

## 1. 决策

### 1.1 工具设计

3 类检查,**3 个独立函数**, 每个报告 1 种 finding:

```python
check_submodule_dirty()      # 类型 1
check_tracked_derived()        # 类型 2
check_submodule_pointer_stale() # 类型 3
```

CLI 模式:
- 默认: 人类可读文本输出, exit 0 (含 findings)
- `--json`: 结构化 JSON
- `--strict`: 任一 finding exit 1 (CI gate 模式)

### 1.2 治本实证

**stamps.json 治本**:
- 主仓 `.gitignore` 加 `runtime/.watch-dispatch-stamps.json` 规则 (ADR-0151 § 1.3)
- `git rm --cached runtime/.watch-dispatch-stamps.json` untrack 已 tracked 文件
- 文件保留本地 (OMO runtime-stamp-policy 写面, 可重建)

### 1.3 .gitignore 新增

```
# ADR-0151 (Round 5f): runtime/.watch-dispatch-stamps.json 是 OMO runtime-stamp-policy
# 守门自动写入的派生面 (每次 bin/gac/omo-state-cleanup.py sync 触发). 主仓 SSOT 跟踪
# metadata (system.yaml, system_health.yaml, health.yaml 等), stamps 本身可重建.
# 治本: 不在主仓 SSOT 中保留. P74 governance boundary 守护.
runtime/.watch-dispatch-stamps.json
```

### 1.4 P74 governance boundary 守住

`check-submodule-hygiene.py` 是**只读守门**(不写任何文件), OMO cron 集成在 OMO 自身 workflow 内
(不在本 ADR 范围).

---

## 2. 不在本 ADR 范围

- ❌ 改 OMO cron (P74 boundary, P3 cron hook 已写 ADR-0144)
- ❌ 4 个 submodule-dirty findings (其他开发者本地状态, 非本任务范围)
- ❌ 改 projects/runtime 子模块 (boundary)
- ❌ 改 runtime 子模块的 .gitignore (boundary)

---

## 3. 关联

- [ADR-0150](./0150-submodule-pr-reverse-review.md) (reviewer 6 步守门)
- [ADR-0149](./0149-p71-baseline-no-replay.md) (防重做)
- [ADR-0129](../projects/ecos/src/ecos/ssot/../../../../../.omo/_knowledge/decisions/0129-state-projection-plane-phase3.md) (派生面范式)
- [ADR-0141](./0141-m2-base-schema.md) (m2 模式一致性)
- [ADR-0148](./0148-round-trip-playbook.md) (round workflow §10)
- [bin/ssot/check-submodule-hygiene.py](./../../../../bin/check-submodule-hygiene.py)
- [.gitignore](./../../../../.gitignore)

---

## 4. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 5f, 3 类子模块卫生守门, stamps.json 治本) |
