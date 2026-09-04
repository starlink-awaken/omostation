---
title: README.zh
type: doc
---

# Kairon

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-purple.svg)](https://docs.astral.sh/uv/)

## 项目定位

知识引擎 monorepo（所属层级：L2；技术栈：Python (uv, pytest)）。

## 安装

```bash
# Clone the workspace recursively
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation/projects/kairon

# Install dependencies with uv
uv sync
```

Requires Python 3.13+ (see `pyproject.toml`).

## 快速开始

```bash
    uv sync
make test-diff
make lint
    ```

    ## Key Surfaces

    - `pyproject.toml`
- `packages/`
- `packages/kos/`
- `packages/eidos/`
- `packages/minerva/`
- `packages/ontoderive/`

    ## Documentation

    - Developer guide: [`AGENTS.md`](AGENTS.md)
    - AI context loader: [`CLAUDE.md`](CLAUDE.md) when present
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer placement: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)

    ## SSOT Rules

    Runtime facts, counts, ports, health, and generated inventories are intentionally not maintained here. Use the workspace registries and project source as the truth.

## 文档

- 英文 README: [`README.md`](README.md)
- 贡献指南: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- 安全策略: [`SECURITY.md`](SECURITY.md)
- 更新日志: [`CHANGELOG.md`](CHANGELOG.md)
- 行为准则: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- 贡献者名单: [`CONTRIBUTORS.md`](CONTRIBUTORS.md)

## 获取帮助

- [FAQ](docs/FAQ.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [API / 使用参考](docs/API.md)
- [架构概览](docs/ARCHITECTURE.md)


---

## 🌐 语言

- [English](README.md)
- [简体中文](README.zh.md)

