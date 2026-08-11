# Contributing

This is a private project. Do not publish it or add a public release workflow.

Use Python 3.13 with uv. Keep implementation changes test-first and place new
tests in the documented layer under `tests/`. The legacy `bin/omlx` behavior is
protected by `tests/test_omlxc.py`; do not change it incidentally while building
v3.

Before proposing a change, run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
```

Never install a development build globally or overwrite the stable system
`omlxc` entry point. Use an isolated virtual environment for console smoke
tests.

