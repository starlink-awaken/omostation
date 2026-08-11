# Project instructions

- Keep v3 work in `src/omlxc` and preserve `bin/omlx` unless a task explicitly
  owns legacy behavior.
- Write a failing test before production code; retain the 32 legacy tests as
  characterization coverage.
- Use Python 3.13, uv, Hatchling, Ruff, and Pyright strict.
- Do not globally install `omlxc`, modify `/opt/homebrew/bin/omlxc`, contact
  real hardware from ordinary tests, or add public-release material.
- Keep personal configuration, secrets, model files, logs, and state out of git.
