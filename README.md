# omlxc

`omlxc` is a private local compute-hub project. Version `3.0.0a1` is the Task 2
installable skeleton for a future `omlxc` CLI and `omlxcd` local daemon. It does
not start a daemon, alter existing local services, contact hardware, or replace
the stable `/opt/homebrew/bin/omlxc` command.

The v3 boundary is intentionally narrow in this task:

- `omlxc --help` and `omlxc --version` work after installation.
- `omlxcd` emits a stable JSON placeholder instead of claiming that an API is
  available.
- `bin/omlx` and its 32 tests remain the legacy characterization baseline.

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
