---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0168-p77-phase5-hardcoded-ports.md
  - 0169-p77-phase6-commit-assist-e2e.md
  - STRAT-P77-strategic-roadmap.md (Phase 7)
  - ../../../../../protocols/port-registry.yaml
  - ../../../../../bin/migrate-port-env-var.py
  - ../../../../../bin/start-gateway.sh
  - ../../../../../bin/gac-mesh-router.py
supersedes: []
---

# ADR-0170: P77 Phase 7 — 端口硬编码 → Env Var 重构 (P77-5-3 治本)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P77 STRAT § 2 Phase 7 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **Env Var 映射 SSOT** | ✅ | `protocols/port-registry.yaml env_vars:` 25 端口映射 |
| **迁移助手** | ✅ | `bin/migrate-port-env-var.py` (scan + suggest + --apply) |
| **root repo 迁移** | ✅ | `bin/gac/start-gateway.sh` (9290→LLM_GATEWAY_PORT), `bin/gac/gac-mesh-router.py` (7437→OMLX_MESH_ROUTER_PORT) |
| **端口类型声明** | ✅ | 7422/7456/8090: `env-only`+ 类型栏 |
| **GaC rule** | ✅ | `CR-ENV-VAR-PORT` (governance-checks.yaml: 172 rules) |
| **catalog 50 原则** | ✅ | p76-principles.md 45→50 (P77-7-1..5) |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

P77 STRAT § 2 Phase 7 入口 (ADR-0168 § 1.5 NEXT):
"端口硬编码 → env var 重构 — 从最高频 port 7430 (agora internal, 16 sites) 开始逐个 env-var 化."

P77-5-3 principle **environment-variable-preferred** 沉淀但从未执行. 39 端口在 SSOT 注册,
25 有 env-only 类型, 但代码中 73 处硬编码字面量.

修真修真反模式:
- `bin/gac/start-gateway.sh`: `--port 9290` 字面量 → 部署不能无修改切换
- `bin/gac/gac-mesh-router.py`: `PORT = 7437` 字面量 → 不能多实例配不同端口
- 16 处 `7430` 在 agora 仓 — 最大单体反模式

### 1.2 WHAT — Env Var 命名规范

```
{服务名大写缩写}_PORT
  例: AGORA_INTERNAL_PORT, LLM_GATEWAY_PORT, OMLX_MESH_ROUTER_PORT

{通用名大写}_PORT
  例: COCKPIT_DASHBOARD_PORT, RUNTIME_L1_PORT
```

默认值 = SSOT 端口号. 代码应写:
```python
port = int(os.environ.get("AGORA_INTERNAL_PORT", "7430"))
```

### 1.3 WHAT — root repo 迁移 (先行)

| 文件 | 旧 | 新 | Env Var |
|------|----|----|---------|
| `bin/gac/start-gateway.sh:12` | `--port 9290` | `--port "${LLM_GATEWAY_PORT:-9290}"` | `LLM_GATEWAY_PORT` |
| `bin/gac/gac-mesh-router.py:17` | `PORT = 7437` | `PORT = int(os.environ.get("OMLX_MESH_ROUTER_PORT", "7437"))` | `OMLX_MESH_ROUTER_PORT` |

### 1.4 WHAT — 迁移模式

本 phase 做: **root repo + SSOT + detector upgrade** (Phase 7a).
留作 submodule PR (Phase 7b+):

| Port | 跨仓 sites | 迁移优先级 |
|------|-----------|-----------|
| 7430 (agora-internal) | 16 | Phase 7b (agora PR) |
| 7422 (agora-mcp-http) | 8 | Phase 7c (agora+omo PR) |
| 8090 (cockpit-dashboard) | 6 | Phase 7d (cockpit PR) |

### 1.5 WHAT — 迁移助手 `bin/migrate-port-env-var.py`

```bash
python bin/migrate-port-env-var.py           # 扫描硬编码端口+env var 建议
python bin/migrate-port-env-var.py --json    # JSON 输出
python bin/migrate-port-env-var.py --apply   # root repo 自动迁移
```

### 1.6 NEXT — Phase 8

| 候选 | ROI |
|------|-----|
| **submodule env var 批量迁移** (7430→agora PR) | 高 |
| **catalog/GaC 健康度基线重放** | 中 |
| **P78 战略规划** | 远期 |

## 2. 沉淀原则 (P77-7)

| # | 原则 | 含义 |
|---|------|------|
| P77-7-1 | **env-var-SSOT** | port→env_var 映射 SSOT 在 port-registry.yaml env_vars 段, 不分散在代码里 |
| P77-7-2 | **literal-fallback** | env var 读取必须有 literal fallback (= SSOT 端口值), 防空 env 时崩溃 |
| P77-7-3 | **env-only-enforcement** | `env-only` 类型端口必须通过 env var 引用, detector 检测字面量 → warning |
| P77-7-4 | **root-first-submodule-later** | 治理工具根仓先行 (SSOT/migration helper), submodule 代码后续逐步迁移 |
| P77-7-5 | **cross-repo-env-contract** | 跨仓间 env var 命名必须一致 (agora 用 `AGORA_MCP_HTTP_PORT`, omo 同) |
