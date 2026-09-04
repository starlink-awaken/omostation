---
title: MIGRATION
type: doc
---

# Migration Guide

## Upgrading Within Major Versions

Patch and minor releases should be backwards-compatible. Update your dependency reference and run your test suite.

## Upgrading Across Major Versions

When a new major version is released:

1. Read the [`CHANGELOG.md`](../CHANGELOG.md) for breaking changes.
2. Update any deprecated APIs.
3. Run integration tests against the new version.
4. Report migration issues on GitHub.

## Migrating From External Alternatives

If you are migrating to `kairon` from a different tool or framework, open a discussion with your use case. Community migration notes may be added here over time.
