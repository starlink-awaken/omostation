# omlxc CLI readability and guided workflow design

## Status

Approved direction for implementation planning. This design changes only the
human-facing CLI experience. Existing JSON, NDJSON, exit-code, daemon API, risk
confirmation, security, and privacy contracts remain authoritative.

## Problem

The current CLI is complete but operator-heavy. Commands expose typed data, yet
new and occasional users must already know which command to run, how to read the
result, and what a safe next step is. Human errors are technically correct but
not consistently actionable. The interactive TUI is useful after discovery,
while non-interactive terminals still need a concise front door.

The goal is to make the correct next action obvious without turning the CLI into
an implicit automation engine.

## Selected approach

Use a shared presentation layer plus a bounded `guide` command.

1. Human-readable commands render a consistent summary, status severity, key
   facts, and zero to three suggested next commands.
2. `omlxc guide` provides a keyboard-driven, read-only decision flow for common
   goals and problems.
3. `--json` and NDJSON bypass the presentation layer and preserve their existing
   byte-level schema and stdout/stderr separation.

This combines immediate readability with guided discovery. It is preferred over
either a documentation-only change, which leaves error recovery weak, or a
large interactive wizard, which would duplicate the TUI and create hidden
mutations.

## User journeys

### First run

`omlxc status` answers four questions in one screen:

- Is the daemon ready?
- Is the system degraded?
- Are there running or stuck jobs?
- What should I do next?

Healthy output ends with optional exploration commands. Degraded output leads
with the problem and suggests the narrowest safe diagnostic command.

### Guided discovery

`omlxc guide` presents a short goal menu:

- Check system health
- Find an available model
- Explain a route decision
- Inspect a running job
- Troubleshoot a daemon problem
- Learn safe model lifecycle commands

The guide may issue only existing read-only daemon calls. For R1/R2 actions it
prints the exact command, impact, confirmation requirement, and rollback; it
never performs the mutation itself.

Non-TTY use of `guide` fails with an actionable message and points to `--help`
or explicit commands. It never prompts in pipelines.

### Error recovery

Human errors use one stable shape:

```text
ERROR E200 · Daemon unavailable
What happened: the private control socket could not be reached.
Next: omlxc daemon status
Request: <request-id>
```

Messages must not expose configuration identity, node identity, network
topology, file paths beyond already-public operator inputs, response bodies,
credentials, prompts, or backend error text. Suggested commands come from a
closed mapping of safe typed error codes and command context; they are never
constructed from untrusted daemon text.

## Architecture

### Presentation module

Add a small presentation module owned by the CLI. It accepts typed daemon data
or typed client errors and returns plain text. It does not perform I/O, inspect
configuration, or call the daemon.

Core concepts:

- `HumanSection`: title plus bounded lines;
- `Guidance`: severity, short explanation, and bounded safe commands;
- renderers for status, node/model/job/route/metric summaries;
- a closed error-code-to-guidance mapping.

The module uses deterministic ordering and no terminal width-dependent content.
Typer remains responsible for command parsing and stdout/stderr. JSON emitters
remain unchanged.

### Guide command

`guide` is a top-level Typer command. A small state machine owns the menu and
steps. Each state declares:

- prompt text;
- available choices;
- one optional read-only client operation;
- result renderer;
- next states or exit.

The state machine has hard bounds: at most eight transitions per invocation,
no recursion, no background tasks, and no automatic retry. EOF, cancellation,
and invalid input exit cleanly without traceback.

### Status enhancement

The existing `status` request remains one daemon health call. Human mode adds a
compact header and guidance derived only from the returned health envelope.
It must not silently fan out into nodes, jobs, metrics, or remote discovery.
Broader information is offered through explicit next commands.

## Compatibility contracts

- All existing command names, options, JSON/NDJSON schema, exit codes, and
  request IDs are unchanged.
- `--json` emits no decoration, color, hints, progress, or prompts.
- Machine output remains stdout-only; errors remain stderr-only.
- Human output is color-free by default so snapshots and copy/paste are stable.
- The TUI remains the no-argument interactive experience. `guide` complements
  it rather than replacing it.
- Risk gates remain authoritative: no guide path calls load, unload, cancel,
  install, start, stop, restart, uninstall, config apply, or rollback.
- Unsupported daemon capabilities stay typed failures; the guide cannot bypass
  the daemon by calling adapters, launchctl, SSH, HTTP backends, or config
  writers.

## Scope

### In scope

- shared human presentation helpers;
- enhanced human `status` output;
- bounded top-level `guide` command;
- actionable safe human errors;
- `--help` examples and a quick-start section;
- unit and integration tests for terminal, non-terminal, JSON, privacy, and risk
  behavior.

### Out of scope

- new daemon endpoints;
- automatic remediation;
- shell completion or plugins;
- fuzzy search;
- network or model probes;
- changing the TUI layout;
- changing config or model lifecycle behavior;
- changing the `/opt/homebrew/bin/omlxc` default entry during this feature.

## Testing

TDD must prove the following behavior before implementation:

1. `status --json` is byte-for-byte unchanged for a fixed envelope.
2. Human healthy, degraded, and unavailable status output is concise and
   contains only closed safe suggestions.
3. Every guide branch is bounded and performs only the expected read-only client
   calls.
4. Non-TTY guide use never prompts and returns the existing config/usage exit
   class.
5. EOF, Ctrl-C, invalid input, daemon typed errors, and malformed responses have
   no traceback.
6. Suggested commands never include daemon message text, identity, URL, path,
   prompt, credential, authorization header, or response body.
7. Existing CLI/TUI, legacy characterization, Ruff, Pyright strict, full pytest,
   warning-as-error, wheel/sdist, coverage, and help-tree tests remain green.

## Acceptance criteria

- A new user can start at `omlxc status` or `omlxc guide` and reach the correct
  explicit read-only command without consulting repository source.
- Common failures identify what happened and provide one narrow safe next step.
- No guide execution mutates service, configuration, jobs, models, Workspace,
  or remote systems.
- JSON and automation consumers observe no schema or output regression.
- Human output is deterministic, bounded, privacy-safe, and testable.

## Rollout

Ship this as a normal reviewed omlxc patch release after the v3.0.2 ACTIVE
observation remains healthy. The feature can be developed and tested in
isolation during observation, but the installed ACTIVE tool and default CLI
entry are not changed until the release and post-observation gates authorize
them.
