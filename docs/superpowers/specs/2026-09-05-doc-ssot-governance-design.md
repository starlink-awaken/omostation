---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T6-17
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-05
---

# 文档 SSOT 全量治理 — 去重/合并/指针化 Design

> 日期：2026-09-05
> 状态：accepted
> BET：BET-Y1Q4-T6-17

## 背景与问题

主仓 + 16 个子仓存在大量 `.md` 文档。当前问题：

1. **SSOT 状态不清**：部分文档是多处重复维护的事实源（doc-ssot-contract 声明了「每份文档拥有一个维度」），但缺少全量判定，无法确认每份文档是否仍在自己的维度内、是否被重复覆盖。
2. **重复内容**：同一知识（架构说明、SOP、规则）在多个文档里重复出现，未指针化收敛。
3. **过时文档**：部分文档被后续 ADR/决策取代但未归档，构成检索噪音。

依据：`.omo/standards/doc-ssot-contract.md`（SSOT 契约）、`AGENTS.md` §2（文档 SSOT 契约表）、`CLAUDE.md`（会话启动协议，声明「不要硬编码运行时值」）。

## 架构选择

**方案：基于现有 doc-ssot-lint 机制做全量判定 + 收敛。**

- 复用 `bin/ssot/doc-ssot-lint.py` 作为判定基线（它已声明各 SSOT 文档的拥有维度），不新增判定引擎。
- 对主仓 + 子仓 `.md` 文档做一次 SSOT 状态盘点，输出**文档索引报告**（每个文档的 SSOT 状态：SSOT / 指针 / 重复候选 / 过时）。
- 对重复内容做**合并或指针化**：能合并的合并（保留 SSOT 源），不能合并的改为指针引用，不复制内容。
- 对过时文档**归档**（移入 `_archive/` 或标注 superseded），不删除有消费者的文档。
- `AGENTS.md` / `CLAUDE.md` 对齐更新（同步本次收敛后的文档分工）。

替代方案：
- 全量重写文档索引（新增独立索引系统）→ 被否：增加表面积，违反 Y1「系统变小」主目标。
- 自动删除疑似重复文档 → 被否：删除有消费者文档是高危操作，需人工复核。

## 验收标准

1. **[文档索引报告存在]**
   - 验证方式：`test -f docs/reports/doc-ssot-inventory-2026-09-05.md`
   - 证据类型：文件存在

2. **[重复内容已合并或指针化]**
   - 验证方式：`git diff --stat` 显示重复内容从多个文档收敛到一个 SSOT 源 + 指针
   - 证据类型：PR diff

3. **[AGENTS.md / CLAUDE.md 对齐更新]**
   - 验证方式：`grep` 确认文档分工表与收敛结果一致
   - 证据类型：diff 审查

4. **[doc-ssot-lint 保持 PASS]**
   - 验证方式：`uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json` exit 0
   - 证据类型：命令退出码

5. **[过时文档已归档或标注 superseded]**
   - 验证方式：索引报告中列出的过时文档均有归档路径或 superseded 标注
   - 证据类型：报告内容

## 反指标

> 对齐蓝图 §20：明确哪些指标不作为成功度量

本 spec **不追求**以下指标作为成功度量：

- 文档总数减少（原因：删除有消费者文档是高危操作；收敛 ≠ 删除）
- 子仓文档全部归主仓（原因：子仓有独立维护责任，SSOT 判定不是集中化）
- 消灭所有重复（原因：跨仓边界存在合理重复，只需指针化消除「内容重复维护」）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 新增文档索引系统 vs 复用 doc-ssot-lint | 复用 | 避免新增表面积，符合 Y1 主目标 |
| 2 | 自动删除重复 vs 人工复核合并/指针化 | 人工复核 | 删除有消费者文档不可自动执行 |
| 3 | 子仓文档是否纳入 | 纳入（子仓需各仓 maintainer 配合） | goal 明确「主仓+子仓」 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-09-05 | 初始版本（T6-17 认领前置） | governance-agent |
