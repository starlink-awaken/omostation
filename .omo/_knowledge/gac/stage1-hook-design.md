# GaC 阶段 1 机制 3 设计 — hook + MCP + CI 多通道 (ADR-0106)

> **机制 3 (泛化执行器) 的跨工具实现**. hook 原型 ✅ done / MCP 待 omo / CI 兜底 ✅.
> 日期: 2026-06-27

---

## 机制 3 的跨工具现实

**Claude Code hook (PreToolUse) 只对 Claude Code 生效**. 其他工具靠 MCP + CI 兜底.

```
┌────────────┬──────────────┬─────┬─────────┬────────────┐
│ 工具        │ PreToolUse   │ MCP │ CI gate │ 覆盖        │
│            │ hook         │     │         │            │
├────────────┼──────────────┼─────┼─────────┼────────────┤
│ Claude Code│ ✅ 本 hook    │ ✅待│ ✅      │ 全通道      │
│ Cline      │ ✅ 类似       │ ✅待│ ✅      │ 全通道      │
│ Cursor     │ 部分         │ ✅待│ ✅      │ MCP+CI      │
│ Codex      │ -            │ ✅待│ ✅      │ MCP+CI      │
│ Devin      │ -            │ ✅待│ ✅      │ MCP+CI      │
│ Aider      │ -            │ ❌  │ ✅      │ CI only     │
└────────────┴──────────────┴─────┴─────────┴────────────┘
```

**GaC `executor` 多通道字段** (`hook_pre_edit`/`mcp_tool`/`ci_gate`) 正为此设计 — 规则声明多通道, 各工具按自己的通道执行. **不把鸡蛋放 hook 一个篮子**.

---

## 通道 1: hook 原型 ✅ done (bin/gac-hook-pre-edit.py)

- **Claude Code PreToolUse**, 拦截 `Edit`/`Write`/`MultiEdit`
- 读 `gac ssot_pointer` 规则, 编辑时即时检查 SSOT 硬编码
- **advisory 模式** (stderr 警告, exit 0 不阻塞)
- 验证三测全过: 硬编码→警告 / 指针引用→静默 / 非 Edit→放行

### 激活配置 (项目级, advisory, 用户决定)

```json
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "command": "python3 bin/gac-hook-pre-edit.py"
      }
    ]
  }
}
```

**注**: 当前不全局激活 (用户决定激活时机). 激活后 Claude Code 编辑时即时 GaC 检查.

---

## 通道 2: MCP 内置 ⏳ 待 (T1.3, omo 无并发)

omo MCP 加 GaC 检查工具 (如 `workspace_edit` 内置 SSOT 检查). **跨工具主力** (Cursor/Codex/Devin 经 MCP).

**阻塞**: omo 并发 (`omo_lint`/`governance_surfaces` 拆分中). 等 omo 无并发 session.

**设计** (待实现):
- omo MCP `check_gac_rule(resource, content)` 工具
- 或 `workspace_edit` 内置 GaC 检查 (agent 经工具, 绕不过)

---

## 通道 3: CI gate ✅ 兜底 (已有)

`.github/workflows/gac-gate.yml`: `gac-validate --gate` 阻塞 + `gac-drift` 报告. **所有工具兜底** (平台层).

---

## 演进路径 (advisory → blocking)

```
当前 (观察期):
  hook advisory (exit 0 + 警告) → 观察 false positive + agent 行为
     ↓
稳定后 (强制期):
  hook exit 2 (阻塞, 强制) → agent 必须修 SSOT drift 才能编辑
     ↓
全通道强制:
  hook (Claude Code) + MCP (omo, 跨工具) + CI (兜底) → 机制 3 全活
```

**advisory 先行** 是有意设计 — 避免 hook false positive 破坏工作流. 稳定后升 blocking.

---

## 测试结果 (hook 原型, 2026-06-27)

| 测试 | 输入 | 期望 | 实际 |
|------|------|------|------|
| ① 硬编码 | `Edit CLAUDE.md "health_score: 88"` | 警告 | ✅ 警告 CR-X4-HEALTH-SSOT |
| ② 指针引用 | `Edit CLAUDE.md "health_score: 88 # 见 system.yaml"` | 静默 | ✅ 静默 (指针合法) |
| ③ 非 Edit | `Read` | 放行 | ✅ 放行 (exit 0) |

---

## 当前状态 (P1 T1.2)

- ✅ hook 原型 `bin/gac-hook-pre-edit.py` (advisory, Claude Code 通道)
- ⏳ MCP (T1.3, omo 阻塞, 跨工具主力)
- ✅ CI gate (兜底)

**机制 3 落地度**: Claude Code 通道 ✅ + 跨工具 (MCP) 待 + CI 兜底 ✅. **Claude Code agent 已可激活 GaC 编辑时强制**.

---

*阶段 1 机制 3 设计 v1.0 · 2026-06-27 · ADR-0106 · hook 原型 done, MCP 待 omo*
