---
type: ssot
owner: governance-team
last-reviewed: 2026-09-05
---

# CLAUDE.md — Obsidian Vault

域入口协议。

## §0.1 操作约束 (l4-kernel Schema)
修改控制面文件时: STATE.md/MEMORY.md 必含 YAML frontmatter (title/status/type/owner/created);
signals.md 信号类型 = ✅⚠️🔴ℹ️; STATUS.md 状态 = STABLE|ALERT|CRITICAL;
control-rules.md CR01-CR03 不可删除。

修改后执行: `l4-kernel domain check obsidian-vault`
error=必须修复 warning=建议修复 info=可忽略

