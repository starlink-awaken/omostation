---
name: analyze-mode
description: "Standardized deep analysis workflow: parallel context gathering with explore + librarian agents, then structured synthesis. Use when asked to analyze code, architecture, configs, or systems before making recommendations."
---

# Analyze Mode — Parallel Context Gathering + Deep Analysis

Use this workflow when the user asks you to **analyze**, **evaluate**, **assess**, or **review** a codebase, architecture, configuration, or system. Do NOT jump to conclusions — gather context first.

## Phase 1: Context Gathering (Parallel)

Launch **2-4 background agents** in parallel to gather context:

| Agent Type | Purpose | When to Use |
|------------|---------|-------------|
| **Explore** | Codebase patterns, implementations, file structures | Always |
| **Librarian** | External docs, official references, GitHub examples | When external libraries or APIs are involved |
| **Grep/AST** | Targeted searches for specific patterns, function calls, imports | For specific code-level questions |

**Rules:**
- Do NOT struggle alone — if the problem is complex, consult specialists
- Use `Grep`, `Glob`, `Bash` for direct targeted searches in parallel with agents
- Collect ALL findings before synthesizing

## Phase 2: Specialist Consultation (If Complex)

If the analysis reveals complex issues:

| Specialist | When to Consult |
|------------|----------------|
| **Oracle** | Conventional problems: architecture, debugging, complex logic |
| **Artistry** | Non-conventional problems: needs a different approach |

## Phase 3: Synthesis

After context gathering completes:

1. **Consolidate findings** from all parallel agents
2. **Identify patterns** — what's repeated, what's anomalous
3. **Classify by severity** — CRITICAL / HIGH / MEDIUM / LOW
4. **Produce structured report** with:
   - Current state summary
   - Findings table (severity | issue | location | evidence)
   - Recommendations (prioritized)
   - Next steps

## Output Format

```markdown
## Analysis: [Topic]

### Context Gathered
- Agents dispatched: N (explore: X, librarian: Y, direct: Z)
- Sources consulted: [list key files/repos/docs]

### Findings

| # | Severity | Finding | Location | Evidence |
|---|----------|---------|----------|----------|
| 1 | CRITICAL | ... | file:line | ... |

### Recommendations
1. [Highest priority action]
2. [Next action]

### Next Steps
- [ ] ...
```

## Anti-patterns

- **DON'T** analyze without gathering context first
- **DON'T** use a single agent when parallel would be faster
- **DON'T** skip synthesis — raw findings without structure are noise
- **DON'T** guess at root causes — trace the evidence chain
