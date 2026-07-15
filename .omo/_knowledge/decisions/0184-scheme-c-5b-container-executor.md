---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0184 — Scheme C Phase 5b: Container Executor 运行时模型

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + agora (I0)

## Context

方案 C Phase 5（证据面）已落地：BOS registry 镜像、mcp_proxy 元数据、CI tip 必跑。
Phase 5b 规划项要求将 **stdio / mcp_stdio spawn** 放入可隔离执行面，限制 FS 与网络，
但此前：

1. `StdioMCPClient` 与 `ProcessPool` 直接 `create_subprocess_exec` / `Popen`，无统一门面。
2. runtime 已有 KEI in-process audit hook（`kei_sandbox`），**不等于** 进程/容器边界隔离。
3. metaos Agent Runtime Phase D 明确：在暴露 Docker socket / 容器管理 MCP 工具之前，
   必须先有 **dedicated container executor**。
4. CI 不能强制依赖 Docker daemon（required checks 需可在无 Docker 的 runner 上绿）。

## Decision

### D1 — 统一 Spawn 门面（agora.execution）

所有 Agora stdio spawn 经 `agora.execution.container_executor`：

| 入口 | 函数 |
|------|------|
| `mcp_proxy.client.StdioMCPClient.connect` | `spawn_async(SpawnSpec)` |
| `mcp.resolver.pool.ProcessPool.get_or_spawn` | `spawn_sync(SpawnSpec)` |

调用方不再自行拼 `Popen` argv（除测试 mock）。

### D2 — 可插拔 Backend

| Backend | 行为 | 默认 |
|---------|------|------|
| `local` | 原生物进程 spawn（与 5b 前等价） | **是**（CI / 开发零依赖） |
| `docker` | `docker run -i --rm` + profile 隔离 flags | 显式 / `auto` 且 daemon 可用 |
| `auto` | docker 可用则 docker，否则 local | 否 |

环境变量：

- `AGORA_SPAWN_BACKEND=local|docker|auto`
- `AGORA_SPAWN_PROFILE=default|trusted-local|strict-netnone`
- `AGORA_SPAWN_STRICT=0|1`（docker 请求但不可用时是否失败）
- `AGORA_SPAWN_DOCKER_IMAGE` / `AGORA_SPAWN_DOCKER_BIN` / `AGORA_SPAWN_PROFILES`

### D3 — Isolation Profile SSOT

文件：`projects/agora/etc/container-executor-profiles.yaml`

默认 `default` profile 目标：

- `--network=none`
- `--read-only` root
- memory / cpus 上限
- `--cap-drop ALL` + `no-new-privileges`
- workspace RO mount + tmp RW mount

`trusted-local`：显式 local-only 直通，**拒绝** docker 包装。

### D4 — 非目标（本 ADR）

- **不** 把 Docker socket 暴露为 agent MCP 工具（metaos Phase D 前置条件）。
- **不** 实现 OS path ACL（那是 Scheme C **5c**）。
- **不** 替换 KEI audit hook；二者正交（in-process vs process boundary）。
- **不** 在 required CI 默认强制 `docker` backend。

### D5 — 证据面

- `describe_executor_status()` 供 doctor / evidence 读取 effective backend。
- L3 spawn 抽样可继续用 host command；可选后续加 docker-wrapped sample。
- unit tests 覆盖 argv 构造、profile 拒绝、strict/fallback，**无需** 真起容器即可绿。

## Consequences

- 生产可渐进：先 `local` 默认上线门面，再对高危 MCP 开 `AGORA_SPAWN_BACKEND=docker`。
- 新增 spawn 路径必须 import facade，禁止平行 `Popen`（后续可用 lint 收紧）。
- Docker 镜像 pin / multi-arch / gVisor 等属后续 hardening，不在本切片。

## Verification

```bash
cd projects/agora
PYTHONPATH=src pytest tests/test_container_executor.py -q
# optional live:
AGORA_SPAWN_BACKEND=docker AGORA_SPAWN_STRICT=0 \
  python -c "from agora.execution import describe_executor_status; print(describe_executor_status())"
```

## References

- `docs/METAOS-ECOS-SCHEME-C.md` Phase 5b
- ADR-0181 (方案 C 三平面)
- ADR-0182 (CI / evidence / BOS)
- `projects/metaos/docs/AGENT-RUNTIME-CONVERGENCE-PLAN.md` Phase D
- `projects/agora/etc/container-executor-profiles.yaml`
- `projects/agora/src/agora/execution/container_executor.py`
