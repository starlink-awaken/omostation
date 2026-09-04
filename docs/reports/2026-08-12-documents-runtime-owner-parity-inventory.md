---
type: ephemeral
created: 2026-09-03
---

# Documents Runtime Source/Owner Parity Inventory

> Date: 2026-08-12
> Scope: Task 7A only — the legacy `@公共/_runtime/**` and `@驾驶舱/_runtime/**` families.
> Method: static inspection of the live `/Users/xiamingxing/Documents` source bytes, source-call references, installed crontab, and existing Workspace owner surfaces. No legacy Documents command was executed for this inventory.

## Boundary and conclusion

Documents remains the content, contract, and evidence plane. Workspace owners
hold execution. This is an inventory, not a cutover: no source command is
bridged, no schedule or client configuration changes, no old source is retired,
and no Documents file is changed.

The two registry families may therefore advance only to `in_progress`. They do
not have per-source owner-command parity, consumer cutover evidence, a
compatibility bridge, or terminal-state evidence.

### Existing owner observations are not replacements

Runtime PR #47 / root PR #1380 registered two manual, read-only generic L4
observations: `l4-registry-list` delegates `l4-kernel registry list --registry
<path> --json`, and `l4-content-audit` delegates `l4-kernel content audit
<Documents-root> --json`. They are not replacement implementations for either
runtime family, have no Documents write scope, and did not change a consumer,
schedule, bridge, or family state.

The available Cockpit `domains_list`, `domain_context`, and `cards_check`
surfaces are likewise read/projection or constraint checks, not command parity
for any source below. `domain_context(cockpit)` reports `execution_policy:
workspace_only`, routes task approval to OMO, and routes knowledge runtime to
Kairon/KOS. `kems status` is an owner observation, not a minute- or daily-job
substitute. The Task 7 brief describes it as a full-L4-audit observation; the
currently inspected Cockpit CLI implementation only renders `workspace_context`
and its separate `kems scan` delegates the L4 scan, so it must not be used as
proof of a scheduled-source replacement without direct parity evidence.

## Evidence method

- SHA-256 values below were read from the live source bytes on 2026-08-12.
- “Active” means a current `crontab -l` entry or executable symlink was found;
  documentation-only references are labelled as such.
- Exit semantics are source-code semantics, not inferred from a green shell
  result. In particular, a script that returns zero after printing findings
  cannot be truthful green evidence.
- No full audit was run, so this inventory deliberately records no live audit
  totals or health counts.

## 公共 runtime sources

| Source and SHA-256 | Interface, current behavior, writes, and exit semantics | Known active consumer(s) | Existing owner relationship and assessment |
|---|---|---|---|
| `@公共/_runtime/watch-dispatch.py`
`812cd98ed529b955f2e641c2e4a11d44056960a586eeffd1a85c3bfba2f6691a` | No flags. Polls registry/MOF, Workspace state/CARDS, and Documents `_inbox`; on mtime change invokes `domain-sync.py --write`, `bridge-refresh.py`, `session-brief.py`, or `weekly-verdict-generator.py`. Writes `Workspace/runtime/.watch-dispatch-stamps.json`. It records a stamp even when a child exits non-zero, prints the child failure, then returns **0**. | Installed `l4-governance-crontab`: every minute. | Scheduling/state belongs in Runtime, but no Runtime job reproduces this watch graph, stamp behavior, or child-exit truthfulness. The current generic L4 jobs are manual observations only. **No parity; active source must remain.** |
| `@公共/_runtime/domain-sync.py`
`c85b58f69ce8cc6c6441f01259bd0073bd0e2dddd25b8df673145f7dace8ee63` | `--emit-index`, `--write`, `--json`; default checks l4-kernel registry, Documents `DOMAIN-INDEX.md`, and ECOS MOF M1. `--write` rewrites the Documents AUTOGEN domain-table block. Returns 1 on detected drift and 2 when essential paths are missing (with the documented MOF setup exception in `--write`). | Installed cron daily 06:00; `watch-dispatch.py` triggers `--write` on registry/MOF changes; `session-brief.py` invokes the default check. | l4-kernel owns registry facts and ECOS owns MOF, but this legacy source still owns the Documents projection write and its exact gate semantics. **No owner command or bridge parity.** |
| `@公共/_runtime/bridge-refresh.py`
`211c73f744a85a2cf6a0f1c1de46517ce96d84ecda9dc23847b01cddfa4dbe65` | `--check` returns 1 when `health.yaml` is stale/unparseable and otherwise 0; `--stdout` is non-writing. Default reads Workspace state/health/CARDS, rewrites two `DASHBOARD.md` AUTOGEN blocks and, if present, updates `METAOS-DASHBOARD.html`; missing Workspace inputs return 2. | Installed cron daily 06:05; `watch-dispatch.py` triggers it on Workspace state/CARDS changes; `session-brief.py` invokes `--check`. | Cockpit/OMO expose related context and CARDS data, but neither is a writer-parity replacement for the Documents dashboard projection. **No owner command or bridge parity.** |
| `@公共/_runtime/session-brief.py`
`3742cb4f0e8be5faa02ec7bb3e49ed3c9c43d39c3517f857f0f960678cc185f5` | Optional `--stdout`; otherwise runs four child gates, reads Workspace/CARDS/signals/KOS state, and writes `@驾驶舱/_control/BRIEF.md`. It renders gate failures into the brief but always returns **0**. | Installed cron daily 06:15; `watch-dispatch.py` invokes it after `_inbox` changes; Documents `CLAUDE.md` §0 uses BRIEF as the startup read artifact. | Cockpit provides context projections; Kairon/KOS owns knowledge runtime. Neither matches the fan-in, BRIEF write, or truthful failure contract. **A printed red gate is not green evidence; no parity.** |
| `@公共/_runtime/check-convergence.py`
`d1aa77da2fd24adba769567ec107b7b79157bbb821633a9ac3e1ab25970205ad` | `--quick`, `--report`, `--base`, `--check-cross-workspace`. Default performs structural/convention/reference/MOF/entity checks, writes history under `@驾驶舱/_generated`, and optionally writes a report. The default path returns normally after findings, so Python exits **0** even for FAIL/WARN findings. `--check-cross-workspace` exits 1 only for critical findings, not warnings. | Installed cron weekly Monday 06:30. | Generic `l4-content-audit` is manual/read-only and is not this source. l4-kernel can own L4 audit logic, but no tested command matches this script's checks, generated history/report, or exit contract. **No parity; default zero cannot be accepted as truthful green evidence.** |
| `@公共/_runtime/check-kems-update.py`
`d824b36907a55462aa7d1fe862e987679b992421f0851b23df5784c61b237f2f` | Pass-through wrapper: derives a mounted domain root, resolves local `kems-toolkit.py`, adds `--root` and optional `_inbox`, and propagates the toolkit exit code. Missing toolkit calls `sys.exit` with a string (non-zero). | Installed cron daily 08:00 calls the `@工作文档/卫健委/_runtime/check-kems-update.py` symlink; both 卫健委 and 国转中心 symlink to this public source. | Kairon/KOS is the execution owner direction, but there is no confirmed Workspace command with per-domain root/inbox/exit parity. **No bridge or cutover; preserve the symlink target and schedule.** |

## 驾驶舱 runtime sources

| Source and SHA-256 | Interface, current behavior, writes, and exit semantics | Known active consumer(s) | Existing owner relationship and assessment |
|---|---|---|---|
| `@驾驶舱/_runtime/check-claude-freshness.py`
`e12b6e7714980f8039143c135c91a6f83109e82fda3232a557d274711998fde6` | No parsed CLI flags. Reads every document-domain `CLAUDE.md`, compares review dates with now, prints status and a pass rate, and writes nothing. It returns **0** even when a domain is missing/stale/yellow/red. | No direct installed-crontab entry found. Legacy operations documents reference manual use, often at obsolete `驾驶舱/scripts` paths. | Cockpit domain/context projections can enumerate domains but do not implement freshness policy or a truthful failure contract. **No source parity; output findings are not green evidence.** |
| `@驾驶舱/_runtime/check-vault-audit.py`
`6aba56abf73d9b576c8898ae281d3b964ead810fa3ced7ba0c2e60f9184e61b8` | No parsed CLI flags. Reads each document domain's `_entities/facts.md` and mtime, prints a table, writes nothing, and returns **0** even when facts files are missing. | No direct installed-crontab entry found; only legacy/manual documentation references were found. | Cockpit can expose domain data, but no owner command has this facts-file audit policy or truthful exit behavior. **No parity; zero exit after findings is unusable as success evidence.** |
| `@驾驶舱/_runtime/ecos-health-check.py`
`2f26b0925c845eaf5a31b1a1f9ae391e650346dfff3dae9d8ae63713a75bff1e` | Optional `--json`. Reads domain index through local `domain_util`; prints/serializes health, KEMS planes, and CLAUDE existence. Returns 1 only when the index cannot load; otherwise returns **0** regardless of red/yellow domain results. | No direct installed-crontab entry found; operations documents advertise manual/CI use at historical `驾驶舱/scripts` paths. | Cockpit `domains_list`/`domain_context` and `kems status` are owner observations/projections, not the same all-domain health policy. **No parity; result colors cannot be collapsed into a zero-exit green gate.** |

## Required next evidence before any further state change

1. For each active source, define one Workspace owner command and direct tests
   for interface, writes, timeout, non-zero propagation, and the source-specific
   negative path.
2. Publish a compatibility bridge and telemetry for every live cron/symlink or
   client consumer; only then seek separately authorized schedule/client cutover.
3. Keep source, consumer, rollback, and confirmation-gate declarations intact
   until the targeted owner implementation and consumer evidence are accepted.
