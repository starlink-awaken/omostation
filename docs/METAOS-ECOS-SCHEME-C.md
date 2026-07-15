# metaos × ecos 方案 C 路线图

> ADR: [0181](../.omo/_knowledge/decisions/0181-metaos-ecos-scheme-c-planes.md)

## 三平面

| 平面 | 拥有者 | 对外前缀 |
|------|--------|----------|
| Policy | ecos core + fabric | `bos://ecos/*` |
| Decision | metaos | `bos://governance/metaos/*` |
| Execution | runtime 等 backend | 经 ecos fabric 分发 |

## 阶段状态

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 基线 | ADR + 本文档 | ✅ |
| 1 契约解耦 | AdmissionPort SPI、L0 义务式、cognitive 去硬路径 | ✅ |
| 2 入口封顶 | metaos MCP deprecated；preflight + metaos fabric backend | ✅ |
| 3 逻辑分区 | partition-map + import lint | ✅ |
| 4 硬化 | MOF 数据包；bus 接线；会话 HMAC；capability YAML | ✅ |
| 5 证据/执行硬化 | BOS registry 镜像同步；mcp_proxy 元数据投影；CI tip 必跑 | ✅ |
| 5b 容器执行面 | container executor 门面 + profile SSOT；stdio spawn 统一入口；docker 可选 | ✅ (ADR-0184) |
| 5c OS 写面 ACL | 设计 0186；L1 doctor 0187；L2 plan/apply 0189（opt-in） | L1 ✅ / L2 ✅ |
| Wave2 UI | cockpit `/api/wave2/dashboard` + UI 面板 ADR-0191 | ✅ |
| Wave2 demo seed | `python -m c2g.demo_seed` ADR-0193 | ✅ |
| 5c setfacl | 细粒度 ACE 设计 ADR-0194；实现另 PR | 📐 设计 ✅ |

## 运行时旋钮

| 变量 | 含义 |
|------|------|
| `AGORA_ADMISSION_PROVIDER` | `module:attr` 指定 admission provider |
| `AGORA_ADMISSION_MODE` | `degraded` / `strict` |
| `AGORA_BOS_INCLUDE_DEPRECATED` | 加载 deprecated BOS 路由 |
| `METAOS_MCP_ALLOW_STANDALONE` | 允许 standalone MCP |
| `ECOS_WF_REQUIRE_PREFLIGHT` | backend preflight 开关 |
| `ECOS_WF_PREFLIGHT_SECRET` | preflight HMAC |
| `METAOS_PREFER_BUNDLED` | 优先认知框架镜像 |
| `METAOS_EVENT_BUS` | `bus` / `http` / `both` / `off` |
| `METAOS_SESSION_INTEGRITY_SECRET` | AgentSession HMAC |
| `METAOS_SESSION_INTEGRITY_REQUIRED` | 强制完整性校验 |
| `METAOS_CAPABILITY_PROFILES` | capability 策略 YAML |
| `AGORA_SPAWN_BACKEND` | stdio spawn: `local` / `docker` / `auto`（5b） |
| `AGORA_SPAWN_PROFILE` | isolation profile 名（5b） |
| `AGORA_SPAWN_STRICT` | docker 不可用时是否失败（5b） |

## Phase 4 命令

```bash
cd projects/metaos
uv run python scripts/sync_cognitive_frameworks.py
uv run python scripts/sync_cognitive_frameworks.py --check
export METAOS_SESSION_INTEGRITY_SECRET='…'
export METAOS_SESSION_INTEGRITY_REQUIRED=1
export METAOS_EVENT_BUS=both
# 策略模板: src/metaos/config/capability-profiles.example.yaml
```

## Phase 3 门禁

```bash
cd projects/ecos
uv run python -m ecos.ssot.tools.partition_import_lint
```

## Phase 5 命令（证据面）

```bash
# BOS registry mirror ↔ bos-services.yaml
uv run --with pyyaml python bin/ssot/sync-bos-registry.py --check
uv run --with pyyaml python bin/ssot/sync-bos-registry.py --write

# evidence score (need agora deps)
uv run --directory projects/agora python bin/gac/evidence-smoke.py --gate 95
```

## Phase 5b 命令（容器执行面）

> ADR: [0184](../.omo/_knowledge/decisions/0184-scheme-c-5b-container-executor.md)

```bash
# 默认 local（与 5b 前行为等价，CI 零 Docker 依赖）
cd projects/agora && PYTHONPATH=src pytest tests/test_container_executor.py -q

# 查看 effective backend / profiles
PYTHONPATH=projects/agora/src python -c \
  "from agora.execution import describe_executor_status; import json; print(json.dumps(describe_executor_status(), indent=2))"

# 生产/红队可选：docker 隔离（需本机 docker daemon）
export AGORA_SPAWN_BACKEND=docker
export AGORA_SPAWN_PROFILE=default   # network=none, read-only, cap-drop ALL
export AGORA_SPAWN_STRICT=0          # daemon 不可用时回退 local；=1 则失败
```

| 旋钮 | 含义 |
|------|------|
| `AGORA_SPAWN_BACKEND` | `local` / `docker` / `auto` |
| `AGORA_SPAWN_PROFILE` | `default` / `trusted-local` / `strict-netnone` |
| `AGORA_SPAWN_STRICT` | docker 不可用时是否硬失败 |
| `AGORA_SPAWN_DOCKER_IMAGE` | 覆盖默认镜像 |
| `AGORA_SPAWN_PROFILES` | 覆盖 profile YAML 路径 |

SSOT: `projects/agora/etc/container-executor-profiles.yaml`  
实现: `projects/agora/src/agora/execution/container_executor.py`  
接线: `StdioMCPClient.connect` + `ProcessPool.get_or_spawn`

## Phase 5c（设计已冻结，实现未做）

> ADR: [0186](../.omo/_knowledge/decisions/0186-scheme-c-5c-os-acl-design.md)

| 层 | 内容 | 状态 |
|----|------|------|
| L0 进程策略 | contract_gatekeeper + direct-omo-io | ✅ 已有 |
| L1 doctor 只读巡检 | `omo lint path-acl`（ADR-0187） | ✅ |
| L2 可选 host ACL | `omo acl plan` / `apply`（ADR-0189，`OMO_OS_ACL=1`） | ✅ |
| L3 容器 | 5b spawn 不 RW mount `.omo` | ✅ 5b |

#运维 Runbook: [`docs/operations/omo-path-acl-runbook.md`](operations/omo-path-acl-runbook.md) (doctor 日常节奏 ADR-0199)

## Phase 5c L1/L2 命令

```bash
cd projects/omo
uv run pytest tests/test_omo_path_acl.py -q
# L1
uv run python -m omo.cli lint path-acl --workspace-root ../.. --json
# L2 dry-run plan (default safe)
uv run python -m omo.cli acl plan --workspace-root ../.. --json
uv run python -m omo.cli acl plan --workspace-root ../.. --acl --json  # named ACE dry-run ADR-0196
# L2 apply (operator only)
# export OMO_OS_ACL=1
# uv run python -m omo.cli acl apply --yes --workspace-root ../..
# uv run python -m omo.cli acl apply --yes --acl --workspace-root ../..  # ACE (ADR-0198)
```

SSOT: `projects/omo/etc/omo-path-acl.yaml`  
**lint 永不** chmod；**apply** 仅 chmod 去 other-write，禁 setfacl/chown。


## Wave2 演示数据

Cockpit Wave2 面板按钮「加载演示数据」→ `POST /api/wave2/demo-seed` (ADR-0197)。
