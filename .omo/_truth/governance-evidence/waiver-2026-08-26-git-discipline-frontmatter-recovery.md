---
lifecycle: history
owner: governance-team
last_updated: 2026-08-26
title: Workflow waiver 证据 — git-discipline frontmatter delimiter 紧急
type: doc
---

# Workflow waiver 证据 — git-discipline frontmatter delimiter 紧急恢复

```text
waiver: user-explicit
when: 2026-08-26
who: xiamingxing
quote: "本次 git-discipline SKILL frontmatter delimiter 紧急恢复跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 .agents/skills/git-discipline/SKILL.md 将 `last-reviewed: 2026-08-26---` 修复为合法 frontmatter，以及 .omo/_truth/governance-evidence/waiver-2026-08-26-git-discipline-frontmatter-recovery.md 记录本句；不得修改 skill 正文、其他文件、BET 状态、completion_evidence 或运行态。"
scope:
  - .agents/skills/git-discipline/SKILL.md
  - .omo/_truth/governance-evidence/waiver-2026-08-26-git-discipline-frontmatter-recovery.md
reason: malformed frontmatter prevents native Skill inspection and therefore fails closed before a governed workflow can start; this is the narrow self-bootstrap correction.
risk: no workflow run, claim, or lock exists for this waiver-scoped repair; normal isolated-clone, review, PR, and CI controls still apply.
residual: resume the registered BET-Y1Q3-T1-12 workflow only after the native Skill inspection and capability preflight pass from merged main.
gate_bypass: 1
no_run_id: true
```

## Hard boundaries

- Do not modify the Skill body, any other file, BET status, completion evidence, or runtime state.
- The only Skill change is splitting the malformed `last-reviewed` line from the closing frontmatter delimiter.
