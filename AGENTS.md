# AGENTS.md — ecos Development Guide

> eCOS v5 L0 Protocol Layer · SSB 签名链 + MOF 元模型 + BOS URI 路由

## Quick Commands

```bash
cd projects/ecos
uv run pytest tests/ -q          # 195 tests
uv run ruff check src/           # Lint check
uv run ruff check --fix src/     # Auto-fix
uv run ruff format src/          # Format
```

## Architecture

ecos 是 eCOS v5 7 层架构的 L0 协议层，负责系统底层的不可变日志和元模型定义。

```
src/ecos/
├── common/      # 公共库 (mcp_vfs, timeout, integrity, pipeline)
├── l0/          # L0 核心
│   ├── ssb/     # SSB 签名链 (auth, client, dump, init, integrity)
│   ├── emergence/   # 涌现计算
│   ├── ssot/    # SSOT 引擎 + 工具链 (25 mof-* 工具)
│   └── symphony/    # 状态机编排
├── cli/         # CLI (dashboard, scheduler, watchdog)
├── services/    # 服务层 (core, governance, integration, monitoring)
├── workflow/    # 工作流
└── ssot/tools/  # MOF 工具链
```

## Key Dependencies

- **外部**: pyyaml, requests, beautifulsoup4, jinja2, fastmcp
- **跨项目**: agora (dashboard/MOF BOS 功能, 通过 try/except 软依赖)
- ecos 是 L0 协议层，不应被上层项目直接 import。跨层通信应通过 MCP/HTTP。

## Testing Pattern

```bash
cd projects/ecos
uv run pytest tests/ -q                     # 全量
uv run pytest tests/ -k "keyword" -q        # 按关键字
```

## File Organization

- `src/ecos/` — 164 源文件, 32,279 行
- `src/ecos/l0/ssot/mof/m1/` — 984 YAML M1 节点 (系统级 SSOT)
- `tests/` — 16 测试文件
- `scripts/` — 41 运维脚本

## Governance Metadata

- **Phase | **9
- **12 个在线域
- **MOF M1**: 5,234 条规则
- **Git**: 74 commits (当期)

## Gotchas

1. **ecos 不应直接 import agora** — 跨层调用应通过 MCP/HTTP
2. **MOF M1 节点** (984 YAML) 是全系统的 SSOT，修改需谨慎
3. **SSB 签名链** 是认知操作的不可篡改记录，不可手动修改
4. **Python >=3.13** — pyproject.toml 要求
