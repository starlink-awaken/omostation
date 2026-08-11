# omlxc

`omlxc` is a private local compute-hub project. Version `3.0.0a1` currently
provides the installable package skeleton plus Task 3's pure domain contract and
versioned configuration migration. It does not start a daemon, alter existing
local services, contact hardware, or replace the stable
`/opt/homebrew/bin/omlxc` command.

The v3 boundary is intentionally narrow in this task:

- `omlxc --help`, `omlxc --version`, and `omlxc config validate|migrate` work
  after installation.
- `omlxcd` emits a stable JSON placeholder instead of claiming that an API is
  available.
- `bin/omlx` and its 32 tests remain the legacy characterization baseline.

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
