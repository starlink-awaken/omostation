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
- no common shell/interpreter command executes Documents `_runtime`,
  `_control`, `.kems/_scripts`, or application-root paths;
- the projection remains below 80 lines.

Focused tests use RED/GREEN coverage for a wrong domain ID, a physical session
worktree reference, application-root execution, common command wrappers, and
Documents-local execution commands. Current focused result: `17 passed`.

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
| `@学习进化/CLAUDE.md` | `9afa26c5be937c9a50cf8a3e97967434de3a1ee28862edf144aaf0cb499b4176` |
| `@学习进化/AGENTS.md` | `abb5bf199665edbaf3ff8c6b940379bb9ea9bcafe868fff0c4d70be9e2b6116f` |
| `@工作文档/卫健委/CLAUDE.md` | `8208a3d74b463b391edd1f50726b4864dfcff3e71fa33e4a1f1ca3d91b6f0a65` |
| `@工作文档/卫健委/AGENTS.md` | `2ab6900df3232eb8ac0a90e8f5f40b4cb8448acc1eda1e56f5d6a980a5843dea` |
| `@创意创作/CLAUDE.md` | `31d7f2ef5768a49a5e7199f321b18dd4e1a42610fb24f1f7e678a57cf8a58683` |
| `@创意创作/AGENTS.md` | `7a93c001c6b1be3763c9c9a7aefe3b58a08303c6c70b119b7efbd7a79573697c` |

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
