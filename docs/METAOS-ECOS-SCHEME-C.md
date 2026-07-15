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
| 5c OS 写面 ACL | `.omo` / `spaces` 目录 ACL 与 broker 对齐 | 📋 规划 |

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

## Phase 5c（规划，未实现）

| 项 | 意图 | 不做的理由（本轮） |
|----|------|-------------------|
| **5c OS ACL** | 对 `.omo`/`spaces` 目录做 unix ACL，仅 broker 进程可写 | 与 launchd/多 agent 本机布局强耦合；先靠 contract_gatekeeper + direct-omo-io |

5c 落地时：先 ADR（ACL 主体列表 + launchd 模型），再实现。
