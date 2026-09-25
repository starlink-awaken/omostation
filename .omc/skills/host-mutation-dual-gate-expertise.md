---
type: ssot
name: host-mutation-dual-gate-expertise
description: omostation 主机写面变更必须 OMO_OS_ACL=1 + --yes 双闸门；plan/doctor/cron 永不 mutation
triggers:
  - OMO_OS_ACL
  - omo acl apply
  - path-acl
  - setfacl
  - named ACE
  - omo-doctor-cron
  - 5c
  - host ACL
  - apply --yes --acl

last-reviewed: 2026-08-26
owner: governance-team
---

# 主机写面双闸门（Scheme C 5c）

## The Insight

**「默认可跑」与「能改 host」必须是两个正交开关。**  
任何会 chmod / setfacl / chown 的路径，在 omostation 都要拆成：

| 层 | 行为 | mutation |
|----|------|----------|
| lint / doctor / cron | 只报 warn | **永远 false** |
| `omo acl plan` / `plan --acl` | 打印脚本 | **永远 false** |
| `omo acl apply --yes` | chmod 等 | 需 **`OMO_OS_ACL=1` 且 `--yes`** |
| `apply --yes --acl` | + named ACE | 同上双闸门 |

缺一即拒绝写 host。CI 与默认 agent 环境 **永不** 设置 `OMO_OS_ACL`。

## Why This Matters

多 agent worktree + launchd/cron 共享一台机上的 `.omo/` / `spaces/`。  
错误 ACL 会砖并发写与守护进程（ADR-0186 设计冻结原因）。  
若把 path-acl 做成 CI hard-fail 或 doctor 自动 apply，runner/本地会随机红或不可恢复。

本轮落地：ADR-0187 L1 → 0189 L2 chmod → 0196 plan ACE → 0198 apply ACE → 0199–0201 doctor/cron/streak **只告警不修复**。

## Recognition Pattern

- 改 `omo.omo_path_acl` / `omo.omo_acl` / `etc/omo-path-acl.yaml`
- 新增 cron / doctor 检查写面权限
- 测试里想「真跑 setfacl」或 CI 里 `export OMO_OS_ACL=1`
- UI 想一键「应用 ACL / apply-tasks / 自动改 GaC」

## The Approach

1. **新能力默认只读**：先 plan JSON，再考虑 apply。
2. **Apply 入口唯一形态**：
   ```bash
   # dry-run（任意环境）
   omo acl plan --acl --json
   # 仅人工 ops 窗口
   OMO_OS_ACL=1 omo acl apply --yes --acl
   ```
3. **单测**：走 `force=True`（或等价）注入路径；**不要**依赖 host 真有 setfacl。  
   Linux 缺 `setfacl` → **soft-skip ACE**，仍可 strip other-write；不是 hard fail。
4. **Doctor / cron / `GET /api/omo/doctor`**：只抬 `path_acl_warn_streak` / ALERT；hint 指向 `omo acl plan`，禁止自动 apply。
5. **Wave2 同类原则**：governance feedback 是 **proposal-only**（`auto_mutate_rules: false`），与 host 双闸门同一哲学——闭环到「人可审的提案」，不闭环到「自动改策略/主机」。
6. **argv-only** 调 setfacl/chmod：禁止 `shell=True` 拼 ACE 脚本。

## Example

```python
# 测试：允许单元测 apply 逻辑，但不打开环境闸门
apply_named_acl_actions(..., force=True)  # CI/单测
# 生产 CLI：无 OMO_OS_ACL → 拒绝，即使传了 --yes
```

手册：`docs/operations/omo-path-acl-runbook.md`  
ADR：0186–0189, 0194, 0196, 0198–0201。
