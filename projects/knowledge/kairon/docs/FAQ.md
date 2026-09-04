---
title: FAQ
type: doc
---

# kairon FAQ

## What is kairon?

kairon is the eCOS v6 knowledge engineering monorepo. See [`../README.md`](../README.md) for a quick overview and [`../CAPABILITY-MAP.md`](../CAPABILITY-MAP.md) for capabilities.

## How do I run tests?

See the **Quick Start** section in [`../README.md`](../README.md).

## How do I contribute?

Read [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md).

## Where are runtime facts (counts, ports, health)?

They are intentionally not maintained in project Markdown. Use the workspace registries:

- [`../../../docs/project-registry.yaml`](../../../docs/project-registry.yaml)
- [`../../../protocols/port-registry.yaml`](../../../protocols/port-registry.yaml)
- [`.omo/state/system.yaml`](../../.omo/state/system.yaml) (via `omo state sync`)

## How do I report a bug or security issue?

- Bugs: open a GitHub issue.
- Security: see [`../SECURITY.md`](../SECURITY.md) for responsible disclosure.

## License

MIT — see [`../LICENSE`](../LICENSE).
