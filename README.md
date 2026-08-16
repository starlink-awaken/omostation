# omlxc

`omlxc` is a private local compute hub. Version `3.3.0` provides a persistent
`omlxcd` control/data plane, a typed Unix-socket client, a scriptable Typer CLI,
and a keyboard-first Textual cockpit. Development and tests do not alter existing
local services, contact real hardware, or replace the stable
`/opt/homebrew/bin/omlxc` command.

The v3 boundary is explicit:

- An interactive `omlxc` opens the eight-page compute cockpit; a non-TTY caller
  must select a command.
- CLI/TUI state and mutations use only the private `omlxcd` Unix socket. Commands
  whose daemon endpoint does not exist return a typed `unsupported` error instead
  of bypassing the daemon.
- JSON and NDJSON include `schema_version` and `request_id`; stable exit codes
  distinguish config, daemon, capacity, timeout, partial, security, and internal
  failures.
- `bin/omlx` and its 32 tests remain the legacy characterization baseline.

Common read-only commands:

```bash
omlxc status
omlxc status --json
omlxc nodes list
omlxc nodes diagnose node-id --json
omlxc models list
omlxc routes plan local/model-id --profile interactive --json
omlxc jobs watch --output ndjson
omlxc metrics show
omlxc daemon status
omlxc doctor --direct --json
```

## Guided CLI quick start

```bash
omlxc status        # cached daemon health plus safe next commands
omlxc guide         # bounded, read-only TTY workflow
omlxc status --json # unchanged machine contract
```

`guide` is TTY-only and bounded. It offers exactly six goals: system health,
available model, route explanation, running job, daemon troubleshooting, and
safe lifecycle command help. `guide` never mutates models, jobs, services, or configuration;
lifecycle guidance prints commands but does not execute them. The no-argument TUI
remains the interactive entry, while status --json is the automation/machine entry.

## 接入本地编码助手

OpenCode、Pi、oh-my-pi、Kilo Code 及其他 OpenAI 兼容客户端应只连接 AetherForge 的受认证
门面；它会通过私有 `omlxcd` Unix socket 使用本地算力。不要让客户端直连 daemon、节点或后端
端口。完整的环境变量、模型发现、四个工具的增量配置、安全边界、流式行为和排障步骤见
[本地 Agent 工具接入指南](docs/local-openai-client-integration.md)。

The OpenAI-compatible chat boundary accepts up to 256 bounded function tools (with a
128 KiB description per tool), assistant `tool_calls`, tool-result messages, and streaming
tool-call deltas. Chat text is
bounded separately at 512,000 characters while the complete request remains
subject to the 1 MiB body limit.

## Backend Adapter Capability Matrix

`omlxc` relies on adapters to translate local hardware requests to backend-specific APIs. Current capability support:

| Capability | oMLX App | LM Studio / LM Link | Ollama |
|---|---|---|---|
| **Chat** | Supported | Supported | Supported |
| **Vision** | *Gap* | Supported | Supported |
| **Embedding**| Implemented (Not advertised) | Implemented (Not advertised) | Supported |
| **Rerank** | *Gap* | *Gap* | *Gap* |

*Note: Embedding endpoints (`/v1/embeddings`) exist for oMLX App and LM Studio under the hood, but are missing from their `AdapterCapability` sets. Rerank capabilities do not yet exist in the architecture.*

Reversible R1 operations require a terminal confirmation or explicit `--yes`:

```bash
omlxc models load local/model-id --yes --json
omlxc models unload local/model-id --yes --json
omlxc jobs cancel job-id --yes --json
```

## Model Benchmark & Resilience

Measure latency (cold/warm load, TTFT) and generation throughput (TPS) across local and remote nodes:

```bash
# Run a benchmark for a specific model or default
omlxc benchmark run coding

# View persisted benchmark leaderboard
omlxc benchmark report

# Explain dynamic EWMA route scoring and circuit breaker states
omlxc routes plan coding --explain
```

The TUI uses `g`, `/`, `:`, `r`, `?`, `q`, and `Esc`. It keeps the last snapshot
visible as `STALE` while reconnecting and degrades its layout below `80x24`.

## Configuration migration

Configuration schema v1 uses TOML and keeps node IDs independent from network
addresses. Runtime precedence is: safe defaults, TOML, `OMLXC_` environment
variables, then one-shot overrides. Environment nesting uses double underscores,
for example `OMLXC_STORAGE__RETENTION_DAYS=45`; values use TOML scalar syntax.

Migration is plan-only unless both confirmation flags are present:

```bash
omlxc config migrate --from /path/to/models.json --target /path/to/config.toml
omlxc config migrate --from /path/to/models.json --target /path/to/config.toml --apply --yes
omlxc config validate --path /path/to/config.toml
```

Persistent writes use private `0600` files, a pre-overwrite snapshot, and atomic
replacement. Credential fields accept Keychain references such as
`keychain://omlxc/backend-name`; plaintext credentials are rejected.

The daemon reads the platform default `config.toml` automatically. Remote
backends require a schema-v1 `tailscale` executable/TTL plus a complete per-node
allowlist (peer ID, node public key, MagicDNS name, tailnet IPs, HTTP ports, and
SSH users). A hostname alone never authorizes discovery. LM Studio SSH control
also requires an absolute private `known_hosts_file`; inference remains direct
HTTP after Tailscale authorization.

## macOS service lifecycle

`daemon install` is plan-only by default. Applying any lifecycle change is R2:

```bash
omlxc daemon install
omlxc daemon install --apply --yes --confirm-impact --json
omlxc daemon start --yes --confirm-impact
omlxc daemon restart --yes --confirm-impact
omlxc daemon stop --yes --confirm-impact
omlxc daemon uninstall --yes --confirm-impact --json
```

The user LaunchAgent always executes `~/.local/bin/omlxcd`. Uninstall keeps data
and logs and reports the recoverable plist backup. `doctor --direct` is strictly
read-only: it does not create SQLite state, change services, write configuration,
or load models.

## Legacy `bin/omlx` release cutover — rebuild `app-models` after every upgrade

The legacy management CLI (`bin/omlx`, distinct from the `omlxc`/`omlxcd` package
above) is deployed as a versioned `git clone` into
`~/.local/share/omlxc/releases/vX.Y.Z`, with `~/omlx` symlinked to the active
release. `models-active/` (the `alias → real weight dir` symlink farm) is
**deliberately committed to git** so it survives every cutover automatically.
`app-models/` (the flat projection oMLX App actually reads its catalog from) is
**deliberately `.gitignore`d** as a machine-local runtime artifact — which means
`git clone`/checkout can never populate it. There is no automated step that
rebuilds it.

**After repointing `~/omlx` to a new release, always run:**

```bash
python3 ~/omlx/bin/omlx app sync --apply
```

Skipping this step leaves `app-models/` empty (or stale). Config-defined aliases
still show up in listings — they are config-canonical — but oMLX App's own
catalog silently collapses, generation/routing fail, and there is no error at
cutover time to say why. `bin/omlx` now prints a one-line warning on every
invocation when this drift is detected (see `_app_projection_health`), but the
sync step itself still has to be run by hand — App model-directory ownership is
human/App territory, `omlx`/`omlxc` warn only and never scan or rewrite it
unprompted. Root-caused and documented 2026-08-15; see
`.omo/_knowledge/audits/omlxc-model-discovery-current-state-2026-08-15.md` in
the workspace root for the fuller inventory-drift investigation this sits next
to.

## Development

Python 3.13 and uv are required. This repository is private and is not a PyPI
or Homebrew release.

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
```

Ordinary `uv run pytest` explicitly deselects `hardware` tests. Run
`uv run pytest -m hardware` only when a real-device smoke has been requested.

To smoke the build without affecting a system command, create an isolated
environment and install the wheel there:

```bash
uv venv --python 3.13 /tmp/omlxc-smoke
wheels=(dist/omlxc-*.whl)
if (( ${#wheels[@]} != 1 )); then
  echo "expected exactly one omlxc wheel" >&2
  exit 1
fi
uv pip install --python /tmp/omlxc-smoke/bin/python "${wheels[0]}"
/tmp/omlxc-smoke/bin/omlxc --version
/tmp/omlxc-smoke/bin/omlxcd
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) for the
development and disclosure boundaries.
