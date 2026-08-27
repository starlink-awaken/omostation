# data/

`data/` is the workspace home for the **shared data substrate**.

This root already exists operationally; Phase 9 formalizes its ownership boundary.

## Current subdirectories

1. `db/` — local database files
2. `backups/` — backup material

## Intended role

Use `data/` for:

1. shared db/index/snapshot/import/export contracts
2. storage locations that are not governance state
3. data assets that are not owned by one project repo alone

Do **not** use `data/` for:

1. `.omo` control truth
2. project source code
3. ephemeral session logs or pid files
