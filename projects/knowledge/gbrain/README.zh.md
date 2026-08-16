# Gbrain

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg)](https://www.typescriptlang.org/)
[![Bun](https://img.shields.io/badge/Bun-runtime-black.svg)](https://bun.sh/)

## 项目定位

Postgres 知识数据库（所属层级：L2；技术栈：TypeScript (bun)）。

## 安装

```bash
# Clone the workspace recursively
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation/projects/gbrain

# Install dependencies with bun
bun install
```

Requires Bun and Node.js (see `package.json`).

## 快速开始

```bash
    bun install
bun test
bun run verify
bun run ci:local
    ```

    ## Key Surfaces

    - `src/core/`
- `src/commands/`
- `src/mcp/`
- `test/`
- `docs/`

    ## Documentation

    - Developer guide: [`AGENTS.md`](AGENTS.md)
    - AI context loader: [`CLAUDE.md`](CLAUDE.md) when present
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer placement: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)

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

