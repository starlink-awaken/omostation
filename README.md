# omlxc

`omlxc` is a private local compute hub. Version `3.0.0a1` provides a persistent
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
omlxc models list
omlxc routes plan local/model-id --profile interactive --json
omlxc jobs watch --output ndjson
omlxc metrics show
omlxc daemon status
```

Reversible R1 operations require a terminal confirmation or explicit `--yes`:

```bash
omlxc models load local/model-id --yes --json
omlxc models unload local/model-id --yes --json
omlxc jobs cancel job-id --yes --json
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
/tmp/omlxc-smoke/bin/python -m pip install dist/omlxc-3.0.0a1-py3-none-any.whl
/tmp/omlxc-smoke/bin/omlxc --version
/tmp/omlxc-smoke/bin/omlxcd
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) for the
development and disclosure boundaries.
