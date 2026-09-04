---
type: ephemeral
created: 2026-09-03
---

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

## 2026-08-13 domain facts reconciliation

The facts gate was closed by adding evidence, not by weakening the audit. Before
the change, the installed command reported nine present and three missing
domains. The missing domains all had source material, so treating the absence as
intentional would have hidden useful structure.

Three minimal facts files were added:

- `@OPC/_entities/facts.md` cites `DOMAIN.yaml`, `ENTITIES.md`, and `INDEX.md`;
- `@工作文档/_entities/facts.md` stays at the federation layer and cites the L4
  registry plus its entity/knowledge routing indexes;
- `@工作文档/合同法规/_entities/facts.md` distinguishes original documents,
  navigation indexes, and derived OCR text.

No volatile counts, customer claims, budgets, or inferred business state were
introduced. Post-change evidence is `status=ok`, total 12, present 12, and zero
missing/unreadable/invalid; all three targeted single-domain calls also return
`status=ok`.

The contracts domain is a nested local Git repository without a remote. Only the
new facts file was committed (`7acdccb`); its unrelated existing modifications,
deletions, and untracked files were not staged. Documents root, OPC, and the
work-docs federation root are not Git repositories, so their facts files remain
installed content-plane artifacts. This evidence closes the facts-surface gap,
not repository cleanliness, whole-domain freshness, or client UI validation.

## 2026-08-13 Claude-3p reload/UI reconciliation

Claude-3p is not a separate application bundle. The installed
`/Applications/Claude.app` runs in `deploymentMode=3p` and uses the independent
`Claude-3p` Application Support and log roots. The user-visible configuration
entrypoint is the **Inference configuration** item under the Gateway account
menu. The applied profile was `CC Switch`; the UI showed provider `Gateway`, a
masked static credential, and the `deepseek-v4-flash` model label. No inference
setting was changed.

The first Developer inspection was intentionally treated as a RED observation:
the Claude process had started on 2026-08-12, before the Claude-3p Cockpit MCP
configuration was updated on 2026-08-13, and `cockpit` was absent from the Local
MCP servers list. After the active Cowork task finished and its deliverables were
visible, Claude was quit cleanly and relaunched. The new process:

- continued to use `~/Library/Application Support/Claude-3p`;
- retained the Gateway deployment and `deepseek-v4-flash` model label;
- directly spawned the accepted Cockpit command under
  `projects/cockpit/.venv/bin/cockpit-mcp`;
- displayed `cockpit` as `running` in Developer settings.

Three unrelated configured servers (`MCP_DOCKER`, `MiniMax`, and
`wps-note-cloud`) reported disconnected and remain truthful client-local debt.
The UI automation could inspect and click the application but could not acquire
keyboard focus for a safe read-only `workspace_context` prompt, so no
Claude-originated tool invocation is claimed. Installed stdio initialize,
tools/list, and direct Cockpit tool-call evidence remains valid command-level
coverage.

This completes the Claude-3p reload/UI MVP, not all-client rollout. The next
client iteration should exercise one real Documents domain journey through the
running Cockpit surface and separately close reload/UI evidence for each other
configured client. Configuration inspection also found existing remote-MCP
credentials embedded in command arguments; their values were not recorded here,
and rotation plus secret-storage migration remains a separate hardening task.

## 2026-08-13 Codex profile and real-journey reconciliation

The Codex journey showed why source-level MCP registration was not enough. The
current client discovered Cockpit correctly, but also started every unrelated
user MCP server. Separately, Codex discovered 235 valid Skills plus two invalid
Skill files; the model prompt could not retain the full catalog with useful
descriptions. The first non-interactive attempts also used the wrong MCP policy:
`auto` can still enter an approval path, whereas the dedicated read-only profile
needs the explicit `approve` value for its four allow-listed Cockpit tools.

The correction is deliberately opt-in and Workspace-owned. The binding registry
now declares a `documents` profile contract. Its generator queries `codex mcp
list` and the app-server `skills/list` protocol instead of copying a machine
inventory into source control. The installed profile disables all MCP servers
except Cockpit and disables only user-scope Skills beneath the user Skill roots;
system Skills and installed document/browser plugins remain available. This
reduced the model-visible list to 17 described Skills and left the default Codex
configuration untouched. Installation is atomic, mode `0600`, idempotent, and
may replace only a stale file carrying the generator marker; caller-owned files
fail closed.

Two evidence boundaries remain important:

- `codex mcp get` does not serialize `required` or
  `default_tools_approval_mode`, even for the existing `runtime` configuration,
  so that command is not used as proof for those fields; the generated TOML,
  registry contract, parser acceptance, and focused tests are the available
  local evidence;
- the bounded fresh `codex exec` run opened external HTTPS connections but
  remained in `SYN_SENT`, so it never emitted a model or MCP tool call. It was
  terminated without writes. The successful direct accepted Cockpit call and
  prior in-app Codex domain call remain separate evidence, not substitutes for
  this missing fresh-client invocation.

Codex still logs the two malformed user Skill files during `exec` before the
profile filter takes effect. Repairing their YAML frontmatter is the next small
client-hygiene task, followed by a retry of the exact read-only
`domain_context(domain_id="work-weijian")` journey when model connectivity is
available. No Documents domain received a client config or executable artifact.

## 2026-08-13 Codex real-journey reconciliation

The previous section remains the record of the first blocked attempt. Its two
open conditions are now resolved. The local shared IMA `knowledge-base` and
`notes` child Skills received valid minimal frontmatter; Codex subsequently
reported 237 parsed Skills and zero errors. Because both paths were already in
the generated disabled-user list, the installed `documents` profile did not
drift and continued to report 13 MCP servers with 219 user-local Skill paths
disabled.

The fresh-client retry used an ephemeral, read-only Codex execution and asked
for only `domain_context(domain_id="work-weijian")`. The model issued exactly
that Cockpit MCP call and exited successfully. Its returned evidence was:

- `binding.status`: `ok`;
- Skill route: accepted Workspace `.agents/skills`;
- Workflow route: accepted Workspace
  `.omo/_truth/registry/agent-workflows.yaml`.

No shell command, local file read, or write tool appeared in the model event
stream. This closes the Codex profile's current model-originated MCP acceptance
gap. The profile remains opt-in, the default Codex config remains untouched,
and Documents domains still contain declarations and content rather than
client/runtime implementations.

## 2026-08-13 Zed profile reconciliation

Zed previously had a valid user-level Cockpit MCP entry, but that alone left
the client free to expose built-in tools and unrelated context-server tools in
the same agent context. The new Workspace-owned `documents` profile closes that
configuration gap without adding anything to a Documents domain.

The installed profile has an empty built-in tool map, disables the catch-all
context-server switch, and enables exactly the four read tools declared by the
`content-domain` registry profile. Matching per-tool permissions allow those
read calls without weakening the existing global confirmation rule. The
installer preserves all unrelated Zed settings, is idempotent, writes mode
`0600`, and fails closed on caller-owned profile or permission conflicts.

Focused profile, registry-checker, and existing Codex regression tests passed.
Using the exact Zed Cockpit command and environment, a direct MCP protocol smoke
initialized successfully, exposed `domain_context`, and returned
`binding.status=ok` for `work-weijian`. That direct smoke proves the configured
server contract, not a Zed-originated model journey. The existing Zed process
started before the settings write, and activating it while macOS remained locked
did not prove a reload. No attempt was made to bypass authentication, and no Zed
Agent Panel green-dot or UI tool-call result is claimed.

This completes the Zed configuration MVP. Remaining client work is deliberately
small and separate: one unlocked Zed model-originated read call, one fresh
Claude-3p domain-tool call, a dedicated decision for ZCode, and remote connector
provisioning before any ChatGPT web acceptance claim.

## 2026-08-13 ZCode native configuration reconciliation

ZCode is a separate Electron application, not another name for Zed. Its native
user-level MCP configuration is `~/.zcode/cli/config.json` under
`mcp.servers`, while workspace instructions are read from the workspace-root
`AGENTS.md`. These locations follow the ZCode documentation for
[MCP services](https://zcode.z.ai/cn/docs/mcp-services) and
[agent instructions](https://zcode.z.ai/cn/docs/agents).

The existing local ZCode configuration already contained a working Cockpit
server entry alongside unrelated third-party model and MCP settings. A direct
stdio protocol smoke using that exact Cockpit command initialized successfully,
listed the expected Documents tools, and returned `binding.status=ok` for
`work-weijian`. No provider, credential, model, or unrelated MCP value was
copied into source control or emitted as evidence.

This change adds a Workspace-owned native JSON contract instead of overwriting
that caller-owned configuration. The new `render`, `install`, and `check`
surfaces manage only `mcp.servers.cockpit`, preserve unrelated settings, write
atomically with mode `0600`, and fail closed for symlink, non-regular, or drifted
targets. The Documents project checker and the required `phase-gate` path now
cover the same declared ZCode contract. Focused configuration, checker, and CI
contract tests pass; the root-wide workflow gate remains unavailable in this
partial worktree because unrelated project submodules and generated runtime
surfaces are intentionally absent.

The evidence boundary remains explicit. The direct protocol smoke proves the
configured server contract, not a ZCode-originated model journey or a per-tool
allow-list that the inspected native configuration surface does not expose.
No client configuration is installed until this change reaches the accepted
Workspace checkout. ChatGPT still has no reviewed public HTTPS MCP endpoint or
Secure MCP Tunnel, so no ChatGPT web acceptance is claimed. The next steps are
to merge this contract, install and re-check the accepted ZCode entry while
proving unrelated settings are preserved, then treat the ZCode model call and
ChatGPT remote connector as separate iterations.

## 2026-08-13 ZCode installation and ChatGPT tunnel MVP reconciliation

The ZCode contract from the preceding section is now merged through Workspace
PR #1401 and installed from the accepted checkout. The installer preserved all
unrelated settings, the post-install checker passed, and a direct stdio smoke
using the exact installed Cockpit command initialized successfully, listed the
declared tools, and returned `binding.status=ok` for `work-weijian`. macOS was
locked, so no ZCode-originated model call or UI reload is claimed.

The ChatGPT iteration deliberately stops at a smaller, reviewable boundary.
Cockpit PR #39 adds a dedicated `cockpit-documents-mcp` entrypoint exposing only
`workspace_context`, `domain_context`, `cards_status`, and `cards_check`. The
Workspace registry owns a matching Secure MCP Tunnel contract and a secret-free
`render`/`check` command. The check fails closed unless the local MCP entrypoint,
`tunnel-client`, the external Platform API key, the tunnel identifier, and
`tunnel-client doctor` are all available. Focused root and Cockpit tests, scoped
format/lint checks, YAML loading, and the live 12-domain contract checker passed.

No Secure MCP Tunnel was provisioned in this iteration. `tunnel-client` and the
two required environment values were absent, and Platform tunnel permissions
and ChatGPT developer-mode state were not assumed. No credential is stored in
the Workspace registry, client configuration, Documents domains, or test
evidence. After this change reaches the accepted checkout, the remaining work
is an explicit external provisioning step followed by a ChatGPT-originated
read-only domain call; neither is represented as complete here.

## 2026-08-13 Runtime facts owner and client-readiness reconciliation

The first Documents execution-layer migration is now live in Workspace without
making Documents a second runtime. Runtime PR #48 merged as `50ee0e9b`; root
PR #1407 merged as `71dd4b9a` and points `projects/runtime` to that commit. The
registered `documents-weijian-facts-audit` job reads the 卫健委 facts surface
through the Runtime Documents plane and writes receipts only to Runtime state.
Its live run validated 271 facts with no errors and four non-blocking warnings
for facts without `entity_ids`; it did not write to the Documents content root.

Current configuration evidence is deliberately separated from model/UI claims:

- the accepted 12-domain project checker returned `ok=true`,
  `domain_count=12`, `gateway_count=12`, and no errors;
- the dedicated Codex Documents profile check returned `ok=true` (13 managed
  MCP entries and 219 disabled user-scope Skill paths);
- Claude Desktop's own configuration contains the Cockpit MCP entry;
- the ZCode native configuration contains Cockpit under `mcp.servers`, retains
  its caller-owned provider and model settings, and now passes the Workspace
  checker with mode `0600`;
- ChatGPT remains **unavailable**, not degraded-to-success: the Secure MCP
  Tunnel client, Platform API key, and tunnel ID are absent. No tunnel,
  credential, or ChatGPT developer-mode connection was created.

The domain-project status projection is therefore complete for local gateway
and Workspace-routing evidence, but not a claim of every client UI journey.
Claude-3p, Codex, Zed, and ZCode UI/model behavior remain bounded by the
per-client evidence already recorded above; ChatGPT requires an explicit
external provisioning decision.

The Documents-side retirement of the old 卫健委 dashboard script is committed
locally on the isolated branch `agent/weijian-runtime-cleanup`
(`32ef724`). The domain repository has no remote and its main worktree is
simultaneously carrying the 271-fact conversion batch, so the cleanup has not
been force-merged into that dirty worktree. This is an intentional pending
integration, not evidence that the content batch or all Documents-local
execution has already been retired.

## 2026-08-13 Runtime KEMS owner parity reconciliation

Runtime PR #51 merged as `64e6823`; Workspace PR #1427 merged as `5a1753444`
and advances `projects/runtime` to that accepted owner. The registered manual
job `documents-weijian-kems-check` reads only the 卫健委 KEMS metadata scope
and the shared inbox, records its baseline and receipt under Runtime state,
and exposes only a bounded change summary. Its focused tests, scoped Ruff
checks, and both Runtime and Workspace pull-request CI runs passed.

An installed-entrypoint smoke invoked
`~/.local/bin/runtime documents run documents-weijian-kems-check --json` with
an isolated Runtime state root. It returned `status=succeeded`, initialized a
zero-change baseline, wrote its baseline and evidence only below that state
root, and left the pre-existing Documents KEMS state file unchanged.

This is owner parity, not a consumer cutover. The `work-runtime` migration
family remains `pending`: the active crontab entry, Claude Scheduled consumer,
and domain-gateway references still invoke legacy paths and have not been
modified. The default shell command `runtime` currently resolves first to the
older `/opt/homebrew/bin/runtime` 0.1.0 entrypoint, which does not expose the
`documents` subcommand; the accepted Runtime entrypoint is installed at
`~/.local/bin/runtime`. Changing PATH precedence or replacing the older global
entrypoint is a separate system-configuration decision and is intentionally
not performed here.

## 2026-08-13 Runtime control-health owner reconciliation

Runtime PR #52 merged as `57b5d54`; Workspace PR #1429 merged as `e63d8dc`
and advances `projects/runtime` to that owner. The registered manual job
`documents-weijian-control-health` is a bounded, read-only health projection:
it reads the Weijian `signals.md` and facts view, writes its receipt only below
the Runtime state root, and does not start or replace the domain-local
controller.

An installed-entrypoint smoke used an isolated Runtime state root. It completed
the projection without a process error and left both Documents inputs unchanged.
The owner correctly returned `exit_code=1` with `status=attention`, rather than
pretending success: the facts view was current, there were no red signals, and
13 warning signals require follow-up. Runtime PR lint/test CI and the complete
Workspace PR gate set passed before merge.

This extends owner parity only. The `work-runtime` migration remains `pending`:
the existing crontab, Claude Scheduled, domain gateway, PATH precedence, and
Documents-local controller consumers are unchanged. Any consumer or schedule
cutover remains a separately confirmed operation.

## 2026-08-14 Cockpit facts and KEMS reconciliation

The Cockpit review separates three intentionally different read surfaces that
an earlier ad-hoc review had conflated:

- `facts-audit` checks only whether the human facts view
  `_entities/facts.md` is present and readable; it is not a YAML-content
  validator.
- `facts-validation work-weijian` reads the bounded Runtime receipt for
  `documents-weijian-facts-audit`. The receipt contract validates the structured
  facts total, type summary, error count, and warning count, including the
  `_entities/facts/_index.yaml` consistency check performed by the Runtime
  owner. The observed 2026-08-14 receipt was `ok` with 271 facts, zero errors,
  and four warnings.
- `kems status` is deliberately a fast control-plane projection. Its `not_run`
  content-audit value means that it has no retained full-scan result; it does
  not mean that KEMS owner reachability failed. A full `kems scan` remains an
  explicit, potentially long-running content-plane audit and returned existing
  content violations in this observation.

Cockpit PR #49 is merged as `bcf4fd8` and adds
`cockpit kems status --json`. It returns the existing stable
`cockpit.kems-status.v1` envelope without parsing terminal formatting; the
exit code remains truthful (`0` only for `ok`, otherwise `1`). A direct smoke
completed promptly with `degraded`, valid L4 registry data, and reachable OMO
and Kairon owners. A separate filesystem check found all 15 KEMS-named
symlinks reachable, so neither a broken link nor an execution timeout explains
the quick-status result.

The current Runtime KEMS and control-health jobs remain useful owner-parity
steps, not a replacement claim for the old scheduled controller. The legacy
controller scans six domain planes, invokes several local checkers, and writes
a daily report inside Documents; `documents-weijian-control-health` reads only
the signals and facts-view inputs and writes its receipt outside Documents.
Likewise, the existing daily crontab still calls the legacy KEMS wrapper.
The next migration must first run an explicit, time-bounded shadow comparison
for each consumer and demonstrate an equivalent Workspace-owned command and
recovery path. Until that evidence and a separate schedule-change approval
exist, the legacy consumers stay active and the migration status remains
`pending`.
