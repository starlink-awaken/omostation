---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-15
related:
  - ../decisions/0186-scheme-c-5c-os-acl-design.md
  - ../decisions/0189-scheme-c-5c-l2-acl-plan-apply.md
  - ../decisions/0198-omo-acl-apply-named-ace.md
source: learner-2026-07-15-stack-retro
---

# Pattern — 主机写面双闸门（Scheme C 5c）

## The Insight

**「默认可跑」与「能改 host」必须正交。**  
lint / doctor / cron / `acl plan` 永不 mutation；`apply` 必须同时满足 **`OMO_OS_ACL=1`** 与 **`--yes`**。CI 永不设置 `OMO_OS_ACL`。

## Why This Matters

多 agent + launchd/cron 共享 `.omo/` / `spaces/`。错误 ACL 会砖并发写。  
同类哲学：Wave2 governance feedback 是 **proposal-only**（`auto_mutate_rules: false`），闭环到可审提案，不自动改 GaC / host。

## Recognition

- 改 `omo_path_acl` / `omo_acl` / `etc/omo-path-acl.yaml`
- 想在 CI 开 `OMO_OS_ACL` 或 doctor 自动 apply
- UI 想一键 apply-tasks / 自动改规则

## Approach

```bash
omo acl plan --acl --json                    # 任意环境
OMO_OS_ACL=1 omo acl apply --yes --acl       # 仅人工 ops
```

- 单测用 `force=True`；缺 `setfacl` soft-skip  
- argv-only，禁止 `shell=True` 拼 ACE  
- doctor/cron 只抬 streak/ALERT，hint 指向 `omo acl plan`

手册：`docs/operations/omo-path-acl-runbook.md`。
