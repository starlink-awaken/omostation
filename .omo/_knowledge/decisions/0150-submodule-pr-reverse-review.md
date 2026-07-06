---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-06
related:
  - 0142-decisions-quick-ref.md
  - 0147-mcptool-adder-guide.md
  - 0148-round-trip-playbook.md
  - 0149-p71-baseline-no-replay.md
  - ../../../../docs/SUBMODULE-PR-REVIEW-GUIDE.md
supersedes: []
---

# ADR-0150: Submodule PR 反向 Review (Round 5e)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

沉淀过去 5 个 submodule PR (#131/#102/#103/#136/#137) 的实战经验:
- **40% 子模块 PR 在创建后即过时 (stale)**,因主仓 .omo/cron 自动 sync 推进 submodule
- 多数 stale PR 是 creator 没 sync main 后即推, 且 PR body 描述的 commit SHA 与 gitlink 实际不符

新增 `docs/SUBMODULE-PR-REVIEW-GUIDE.md` 双角度导引:
- **提交者**: 5 步自检 + OMO cron 兼容性
- **Reviewer**: 6 步守门 + close 模板

**避免重做历史坑**: PR #102 + #137 都是同一模式(creator 推 submodule bump, 落后 main HEAD 多个 commit, PR body 与 gitlink SHA 不一致), 关闭评论模板要写出证据。

---

## 1. 三种 submodule PR 模式 (历史归类)

| 模式 | 例子 | 创建后是否过时 |
|------|------|----------------|
| **A. 匹配** | #131 (R0..R5 大闭合 PR), #136 (omo debt fix) | 否, 但与 main HEAD 完全一致, 实质 no-op |
| **B. 落后** | #102, #137 | 是, creator push 后 main 已推进 |
| **C. 真补** | #103 (P110-A 修复) | 否, 真补充未覆盖代码 |

---

## 2. 决策

### 2.1 双角度 checklist

**提交者 5 步**:
1. 同步主仓 main
2. submodule SHA 比对 (vs main HEAD)
3. PR body commit SHA 与 gitlink 一致性
4. 5-check strict + 57 测试本地全绿
5. push + PR

**Reviewer 6 步**:
1. PR createdAt vs main HEAD 活动
2. submodule SHA diff 表 (主表)
3. PR body SHA 与 gitlink SHA diff
4. M4 Health Score 影响预估
5. merge --no-commit 本地兼容性
6. OMO cron 边界守住 (不动 .cron/*.truth/*.state/)

### 2.2 close 模板标准化

close 评论必须含:
- submodule bump 落后证据 (表格)
- PR body SHA 不一致证据 (如有)
- merge 后会丢失的 commits 列表

### 2.3 与既有 ADR 网整合

- ADR-0142 决策速查新增一行 (Submodule PR Reverse Review)
- ADR-0148 Round-trip §10.1 加 R-submodule-bump 类型
- ADR-0147 单 PR 模板对应 submodule PR 自检路径
- AGENTS.md §10 round workflow 第 5 步 ADR review 加注 submodule PR 引用 ADR-0150

---

## 3. 不在本 ADR 范围

- ❌ 自动 reject 工具(`bin/reject-stale-pr.py` 之类) — 增加入侵, 不在本 round 范围
- ❌ 改 OMO cron 自动 sync (P74 四条规则已有守门)
- ❌ PR template 全面变更 — 单独 ADR

---

## 4. 关联

- [ADR-0142](./0142-decisions-quick-ref.md)
- [ADR-0147](./0147-mcptool-adder-guide.md)
- [ADR-0148](./0148-round-trip-playbook.md)
- [ADR-0149](./0149-p71-baseline-no-replay.md)
- [docs/SUBMODULE-PR-REVIEW-GUIDE.md](./../../../../docs/SUBMODULE-PR-REVIEW-GUIDE.md)

---

## 5. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 5e, 5 PR 实战沉淀, 提交者+reviewer checklist) |
