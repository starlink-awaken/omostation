# Test layout

`test_omlxc.py` is the 32-test legacy characterization suite for `bin/omlx`.
It deliberately remains executable without live model hardware and preserves the
baseline's observable behavior while v3 is built beside it.

New work belongs in a layer:

- `unit/` — pure package behavior and future domain/application code.
- `contract/` — reusable backend-adapter contracts.
- `integration/` — controlled process, HTTP, Unix-socket, and SQLite tests.
- `tui/` — Textual behavior tests.
- `hardware/` — explicitly marked real-device smoke tests; ordinary `pytest`
  must never initiate a hardware connection.

