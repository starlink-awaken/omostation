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
| 5 证据/执行硬化 | BOS registry 镜像同步；mcp_proxy 元数据投影；CI tip 必跑 | ✅ (本轮) |
| 5b 容器执行面 | container executor 隔离 spawn（独立 PR） | 📋 规划 |
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

## Phase 5b / 5c（规划，未实现）

| 项 | 意图 | 不做的理由（本轮） |
|----|------|-------------------|
| **5b container executor** | 将 stdio/mcp_stdio spawn 放入容器/sandbox，限制 FS 与网络 | 需要 runtime 调度契约 + 镜像 SSOT；单独立项避免与 CI 收口混 PR |
| **5c OS ACL** | 对 `.omo`/`spaces` 目录做 unix ACL，仅 broker 进程可写 | 与 launchd/多 agent 本机布局强耦合；先靠 contract_gatekeeper + direct-omo-io |

下一步落地时：先 ADR（executor 运行时模型 / ACL 主体列表），再实现，再把证据 smoke 加 L3 spawn 抽样。
