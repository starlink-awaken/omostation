---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T6-21
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-06
type: ephemeral
---

# BET-Y1Q4-T6-21 retro — Documents 多客户端配置自愈与 BOS 统一事实网关

## What changed

- **`bin/gac/documents-client-sync.py`**（主体交付，check/apply 双模式 +
  --json）：真实主机实测发现 4 处 drift 并自愈（claude_desktop repaired /
  codex created / zed repaired / zcode repaired——全部对齐 managed MCP
  server 'cockpit'）；apply 后 check 恢复一致（OK no drift）。
- **agora `tools_bos/documents.py`**（收口修复，40081a6 已进 agora main）：
  三个 handler 修复 registry 路径解析（优先可 patch 的
  `_DOMAIN_REGISTRY_FILE` 常量）+ registry 返回补
  `client_contracts`/`schema_valid` 契约字段 + state env var 固定为
  `OMOSTATION_RUNTIME_STATE_ROOT`——三处"实现与测试契约脱节"全修。
- 测试：agora facade 15/15 + root client-sync 8/8，ruff clean。

## Q3 (打假)

- 首版实现三处 handler 全部绕过可 patch 常量——单测 patch 全失效
  （7 失败）。教训：模块级常量作为契约 seam 暴露后，handler 必须消费它。
- state 的 env var 名首版从 registry config 读；测试契约是固定协议名——
  固定协议名优先，config 只做 default。
- worktree 反复被并发清理两次（本会话与并发 agent 撞 worktree 生命周期）
  ——最终用独立命名的 b 后缀 worktree 完成收账。

## Q4 (遗留)

- drift 检测只覆盖 managed MCP server 段（防自愈过度，设计如此）。
- Documents registry 的 apiVersion 演进策略待后续。
