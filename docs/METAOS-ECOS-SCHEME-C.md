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
