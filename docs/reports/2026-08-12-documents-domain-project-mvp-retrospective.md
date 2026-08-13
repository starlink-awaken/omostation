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
- the ChatGPT Web routing boundary is truthful: developer mode accepts public
  HTTPS MCP or Secure MCP Tunnel and does not consume local Claude/Codex JSON;
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

## Historical snapshot (pre-installation, preserved)

The local client deployment is not yet ready:

- Codex, Claude Desktop, and both inspected Zed settings files contain no
  Cockpit MCP registration.
- `/Users/xiamingxing/.local/bin/cockpit{,-mcp}` still points to the older
  `/Users/xiamingxing/Workspace/projects/cockpit/.venv` installation.
- The installed `cockpit context` and `cockpit cards --check` currently return
  `L4 bridge unavailable` with exit code 1.

Therefore this historical snapshot proved gateway and accepted-source behavior
before the user-level installation transaction. It is retained as history; the
current installed-entrypoint result is recorded in the dated reconciliation below.

## Retrospective

1. The original first draft embedded a session worktree path. The new checker
   caught the architectural issue before PR delivery; client projections now
   name a logical authority and let Cockpit resolve its accepted checkout.
2. A green source-level MCP test is not evidence that desktop clients are
   configured. Configuration presence and installed-entrypoint smoke must be
   separate acceptance gates.
3. The selected-domain option keeps MVP verification fast while remaining the
   same checker that will later enforce all 12 domains.

## Historical next steps (pre-installation snapshot)

1. Prepare and review a single client installation/configuration transaction,
   then request exact user confirmation before applying it.
2. Register one real low-risk read-only Runtime Documents owner job and prove
   dry-run, success, owner non-zero, evidence, and no-write-back behavior.
3. Run local project smoke in Claude/Codex/Zed, then close the MVP acceptance
   report before expanding to 12/12 domains.

## 2026-08-12 installed Cockpit/MCP smoke reconciliation

The accepted user-level Cockpit installation was exercised directly on
2026-08-12. The first four installed commands are accepted exactly as observed:

| Invocation | Observable result | Acceptance |
|---|---|---|
| `/Users/xiamingxing/.local/bin/cockpit context` | exit 0; status `ok`; Documents `12/12` | accepted |
| `/Users/xiamingxing/.local/bin/cockpit cards --check` | exit 0; compliant; OMO exit 0; scope `all` | accepted |
| `/Users/xiamingxing/.local/bin/cockpit kems domains` | exit 0; 12 domains; L4 registry source | accepted |
| `/Users/xiamingxing/.local/bin/cockpit kems status` | exit 1; `degraded` because the L4 content audit truthfully reports existing violations; OMO and Kairon owners `ok` | accepted as truthful degraded status |
| `L4_DOCUMENTS_ROOT="/Users/xiamingxing/Documents" /Users/xiamingxing/.local/bin/cockpit kems scan` | non-zero full audit; not green | remains open |

The accepted `cockpit-mcp` stdio server was independently exercised. Initialize
succeeded; `tools/list` reported 17 tools; and `workspace_context`,
`domain_context(vault)`, and `cards_check` each returned JSON-RPC success with a
status-`ok` business envelope. This proves the installed Cockpit binary and MCP
protocol surface, not Claude, Codex, Zed, or ChatGPT UI reload. It does not
provision a ChatGPT Secure MCP Tunnel.

The same full Documents L4 audit completed non-zero with 322,871 artifacts,
41,987 violations, 5,097 runtime artifacts, 36,867 cache artifacts, 1 bridge,
31,441 content archives, and 23 `invalid_archive` artifacts. Live filesystem
changes were observed while scanning, so `L4-CONTENT-011` was emitted as
designed. This is content-plane debt, not an installed-entrypoint failure; the
overall completion contract and physical migration confirmation gates remain
unchanged.

## 2026-08-12 status reconciliation

This addendum preserves the Phase 6 snapshot above and records the accepted
post-snapshot state:

- root PR #1372 makes the source-level gateway checker live green for 12/12
  domains;
- the configuration transaction covers Codex, standard Claude, Claude-3p, and
  one Zed/ZCode configuration; the installed Cockpit/MCP smoke is now recorded
  above, while each client's reload and UI smoke remains separately unverified;
- root PR #1366 / commit `aa43a79d` completed the governed manifest owner job
  with dry-run, success, owner nonzero, evidence, and no-write-back proof;
- no ChatGPT Secure MCP Tunnel was provisioned;
- no current Codex or Zed UI smoke is claimed.

Historical step 1 is superseded for the recorded configuration transaction,
but not for each client's reload/UI smoke. Historical
step 2 is completed by PR #1366 / `aa43a79d`. The 12-domain expansion clause
in historical step 3 is superseded by PR #1372; its client-smoke work remains
pending.

Current non-destructive next steps are to retain live 12/12 checker evidence,
perform and record each client's reload/UI smoke independently, review the
official ChatGPT public HTTPS/Secure MCP Tunnel
requirements without provisioning a tunnel or handling credentials, and
continue physical migration, cache-cleanup, retirement, Zotero, family-app,
external-repository, and T8 work under their existing evidence and
confirmation gates.

## 2026-08-12 correction — ChatGPT MCP routing

Official OpenAI evidence supersedes the prior “remote plugin only” assumption.
ChatGPT developer mode connects either a public HTTPS MCP endpoint or a Secure
MCP Tunnel; local Claude/Codex JSON is not consumed. The official references
are <https://developers.openai.com/plugins/deploy/connect-chatgpt> and
<https://developers.openai.com/api/docs/guides/secure-mcp-tunnels>. This task
did not provision a tunnel: credentials and external Platform state remain a
separate, owner-confirmed operation.

## 2026-08-13 capability-owner convergence reconciliation

The MVP originally named Workspace as the skill/workflow owner but routed both
capabilities through Documents `bos://` indexes. That was a semantic split:
human projections could drift while the checker and Cockpit still reported a
healthy binding.

The split is now closed through two merged changes:

- Cockpit PR #38 / merge `78af7865` validates capability owners and
  Workspace-relative sources, derives their installed paths, and returns a
  degraded binding for an invalid route;
- root PR #1391 / merge `536b0d97` points skills to `.agents/skills`, workflows
  to `.omo/_truth/registry/agent-workflows.yaml`, adds RED/GREEN contract
  coverage, records ADR-0409, and installs the Cockpit pointer.

Observed verification after installation:

- both repositories' remote lint/test and root governance checks passed;
- the installed Documents checker returned `ok=true`, `domain_count=12`,
  `gateway_count=12`, and no errors;
- twelve direct installed `domain_context` calls all returned `status=ok`;
- their route evidence resolved under the accepted Workspace checkout, not
  under Documents;
- Codex, standard Claude, Claude-3p, Zed, and ZCode configuration still point
  to the same accepted `cockpit-mcp` command and L4 registry environment;
- `@公共/_control/SKILL-INDEX.md` and `REGISTRY.md` were relabeled as human
  projections with no inventory-row deletion; the exact pre-change files are
  backed up at
  `/Users/xiamingxing/.local/state/omostation/backups/20260813T1029+0800-documents-capability-route-projection/`.

The current `facts-audit` remains truthfully non-green: nine domains have a
facts artifact and three do not (`opc`, `work-docs`, `work-contracts`). This is
the next content-quality iteration, not a reason to create empty facts files or
to reopen the capability-route work. Per-client reload/UI evidence and ChatGPT
tunnel provisioning also remain unclaimed.
