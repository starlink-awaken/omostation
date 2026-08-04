---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-08-05
related:
  - ../_knowledge/decisions/0372-memory-os-control-plane.md
  - ../_truth/registry/memory-os.yaml
  - ../../docs/operations/memory-os-neo4j-local.md
---

# Memory OS 运维契约（Phase 8）

## 目的

把 Memory OS 从「代码已合」推进到「进程默认可连图」——声明/执行一致。

## SSOT

| 事实 | 路径 |
|------|------|
| 控制面登记 | `.omo/_truth/registry/memory-os.yaml` |
| RBAC 策略表 | `.omo/_truth/registry/memory-rbac.yaml` |
| 架构 | `docs/architecture/memory-os.md` |
| 本机图运维 | `docs/operations/memory-os-neo4j-local.md` |
| 环境模板 | `docs/operations/memory-os.env.example` |
| 端口 | `protocols/port-registry.yaml` · 7474 / 7687 |

## 环境注入（必须）

Agent / cockpit / cron 调用 mos 前：

```bash
source bin/memory-os-env.sh
# 或
eval "$(bin/memory-os-env.sh --export)"
```

加载优先级（**已设置的非空环境变量永不覆盖**）：

1. 进程现有 env  
2. `config/memory-os.env`（本机私密，gitignored）  
3. `projects/cockpit/.env`  
4. `docs/operations/memory-os.env.example` 默认值  

关键变量：`NEO4J_URI` · `NEO4J_USER` · `NEO4J_PASSWORD` · `MOS_RBAC` · `MOS_TEMPORAL`

## 图库启动

```bash
bash bin/memory-os-neo4j-up.sh          # Docker/podman → brew
bash bin/memory-os-neo4j-up.sh status
```

## 诚实边界

- 无 `NEO4J_URI` → 不写图、recall 不 fan-out neo4j（status 标明）  
- 不得声称 graphiti-core 生产就绪（Cypher FACT + TemporalShadow）  
- 密码不得写入仓内 SSOT（仅 example 默认 `changeme`）

## 治理检查

```bash
python3 bin/gac/check-memory-os-surfaces.py
make memory-os-check
```

必过：SSOT 文件存在 · env.example 键齐全 · 7474/7687 已注册 · cockpit `.env.example` 含 NEO4J_URI。
