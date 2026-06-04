# Hermes Console

Unified UI for the omostation platform. Pure MCP (Model Context Protocol) client.

## Purpose

Hermes Console provides a single-pane-of-glass interface across four operational views:

| View | Description |
|------|-------------|
| **Knowledge Dashboard** | Knowledge graph overview, ontology browser, semantic search |
| **Agent Console** | Multi-agent orchestration, task dispatch, run logs |
| **Health Monitor** | System metrics, service status, alert history |
| **Settings** | MCP endpoints, user preferences, theme config |

## Stack

- **React 18** (functional components + hooks)
- **TypeScript 5**
- No external UI library — plain CSS-in-JS via inline styles

## Quick Start

```bash
cd projects/hermes-console
npm install
npm run dev      # start dev server (port 3000)
npm run build    # production build to build/
npm test         # run tests
npm run lint     # type-check + eslint
```

## Architecture

```
src/
├── App.tsx          # Shell: NavBar + View routing + MCP context
├── index.tsx        # ReactDOM entry point
└── (future)         # hooks/, components/, views/
```

All state flows through React context. The MCP client is a stub hook (`useMcpClient`) that will be backed by a real JSON-RPC transport in future iterations.

## Related Projects

- [kairon](../../kairon/) — Knowledge engineering stack (Python)
- [agentmesh](../../agentmesh/) — Multi-agent SDK (TypeScript)
- [gbrain](../../gbrain/) — Postgres knowledge brain (TypeScript)
