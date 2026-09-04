---
title: RELEASE
type: doc
---

# Release Process

This document describes how to cut a new release for `kairon`.

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

- `MAJOR` — incompatible API changes
- `MINOR` — backwards-compatible functionality
- `PATCH` — backwards-compatible bug fixes

## Release Checklist

- [ ] All tests pass on `main`.
- [ ] `CHANGELOG.md` is updated with the new version and date.
- [ ] Version strings are bumped (e.g. `pyproject.toml`, `package.json`).
- [ ] A release PR is reviewed and merged.
- [ ] A Git tag `v<VERSION>` is pushed.
- [ ] GitHub Release notes are published.

## Post-Release

- [ ] Update the workspace root submodule pointer if applicable.
- [ ] Announce the release in the workspace release notes.
