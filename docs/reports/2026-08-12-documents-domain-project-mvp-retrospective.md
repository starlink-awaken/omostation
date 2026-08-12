# Documents Domain Project MVP — Phase 6 Retrospective

Date: 2026-08-12

## Outcome

The first three standalone Documents projects now use thin client projections:

| Domain | Identity SSOT | Claude projection | Codex/Zed projection |
|---|---|---|---|
| `vault` | `@学习进化/DOMAIN.yaml` | `@学习进化/CLAUDE.md` | `@学习进化/AGENTS.md` |
| `work-weijian` | `@工作文档/卫健委/DOMAIN.yaml` | `@工作文档/卫健委/CLAUDE.md` | `@工作文档/卫健委/AGENTS.md` |
| `creative` | `@创意创作/DOMAIN.yaml` | `@创意创作/CLAUDE.md` | `@创意创作/AGENTS.md` |

Each projection is 17 lines. It restores the manifest ID, requests
`domain_context(domain_id=...)` from the client-scoped Cockpit Workspace MCP,
uses only the returned capability routes, and fails visibly as `degraded` when
the MCP is unavailable. It does not copy domain metadata, a tool matrix, a
Skill/Workflow inventory, or execution code.

The projections refer to the logical Workspace binding registry
`documents-domain-projects`, not a physical checkout. This matters because the
active `~/Workspace` checkout can legitimately be a different dirty branch;
hard-coding either that path or a session worktree would turn deployment state
into a third authority.

## Automated acceptance

`documents-domain-project-check.py` now accepts repeated `--gateway-domain`
arguments. For selected domains it resolves the domain root through the
validated L4 manifest registry and verifies both client files:

- `DOMAIN.yaml` remains the identity SSOT;
- the requested `domain_context` ID equals the manifest ID;
- the logical Workspace binding registry is named without binding a worktree;
- degraded and default-read-only behavior are explicit;
- the ChatGPT Web remote-plugin boundary is truthful;
- no shell/Python/Node command executes Documents `_runtime`, `_control`, or
  `.kems/_scripts` paths;
- the projection remains below 80 lines.

Focused tests use RED/GREEN coverage for a wrong domain ID, a physical session
worktree reference, and a Documents-local execution command. Current focused
result: `10 passed`.

The live three-domain check returned:

```json
{"ok": true, "domain_count": 12, "gateway_count": 3, "errors": []}
```

Direct calls against the accepted Cockpit checkout returned `status=ok`, the
correct identity for all three domain IDs, profile `content-domain`, execution
policy `workspace_only`, and the same four allowed read tools.

## Content-plane evidence

No `DOMAIN.yaml`, content file, historical script, or directory layout was
changed. Only the six explicitly authorized client projections changed. Their
post-change SHA-256 values are the immutable evidence for this phase:

| Projection | SHA-256 |
|---|---|
| `@学习进化/CLAUDE.md` | `482f475d14eb3d60648cccd100db2c0ced6121b2c84b867346a90db2663264df` |
| `@学习进化/AGENTS.md` | `9f81a0a171a140d4a4842321876f5c635336c3641002f24d2a8d9efcc16323e5` |
| `@工作文档/卫健委/CLAUDE.md` | `9ad6fe234bf4747b2350c1ee2d34a5d12a588ae042ffe7834fe6fdd6ee324495` |
| `@工作文档/卫健委/AGENTS.md` | `a41f333d40a93b101d5aaac2ab6b0c4ea70fcb1b6dc8c4f5a69b4bc86757a90e` |
| `@创意创作/CLAUDE.md` | `eb1537aa397f9be85294f0a71f8939ddfa074229e2fbc3fa2cc163d3e0ca8b39` |
| `@创意创作/AGENTS.md` | `c59f2b425b71deb8dae39d3f50a039c37cd665ed0f7474ad67c4882651c00996` |

## Honest remaining gap

The local client deployment is not yet ready:

- Codex, Claude Desktop, and both inspected Zed settings files contain no
  Cockpit MCP registration.
- `/Users/xiamingxing/.local/bin/cockpit{,-mcp}` still points to the older
  `/Users/xiamingxing/Workspace/projects/cockpit/.venv` installation.
- The installed `cockpit context` and `cockpit cards --check` currently return
  `L4 bridge unavailable` with exit code 1.

Therefore this phase proves gateway and accepted-source behavior, but does not
claim end-user client installation. Updating a user package and three global
client configurations is a separate high-risk operation and remains behind an
exact confirmation gate.

## Retrospective

1. The original first draft embedded a session worktree path. The new checker
   caught the architectural issue before PR delivery; client projections now
   name a logical authority and let Cockpit resolve its accepted checkout.
2. A green source-level MCP test is not evidence that desktop clients are
   configured. Configuration presence and installed-entrypoint smoke must be
   separate acceptance gates.
3. The selected-domain option keeps MVP verification fast while remaining the
   same checker that will later enforce all 12 domains.

## Next MVP steps

1. Prepare and review a single client installation/configuration transaction,
   then request exact user confirmation before applying it.
2. Register one real low-risk read-only Runtime Documents owner job and prove
   dry-run, success, owner non-zero, evidence, and no-write-back behavior.
3. Run local project smoke in Claude/Codex/Zed, then close the MVP acceptance
   report before expanding to 12/12 domains.
