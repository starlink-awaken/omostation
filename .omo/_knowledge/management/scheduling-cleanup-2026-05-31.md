# 调度基础设施清理记录

> **日期**: 2026-05-31
> **范围**: cron-service / hermes 桥接层 / launchd / crontab
> **触发原因**: 项目迭代导致 5 个项目（eCOS、wksp、Forge、iris、agent-runtime）被归档/删除，所有调度脚本不可用

---

## 背景

Hermes 桥接架构中，`~/.hermes/scripts/` 存储了指向各项目 `scripts/` 目录的 symlink。cron-service、crontab 和 launchd 均通过该桥接层引用实际脚本。5 个项目的删除导致 179 个 symlink 断裂，所有定时任务失效。

**已归档/删除的项目**：eCOS、wksp、Forge、iris、agent-runtime、kos（部分丢失 scripts/）

**仍活跃的项目**：kairon、SharedBrain（scripts/ 目录已删除）、gbrain、agentmesh、omostation（root）

## 清理操作

### 1. 删除 179 个断裂 symlink (`~/.hermes/scripts/`)

- **结果**: 完成。清理由脚本遍历完成，仅保留非 symlink 内容
- **保留的文件**: `x2-backup-brain`、`arcnode/`、`INDEX.md`、`SECRETS_INVENTORY.md`、`.pytest_cache/`、`__pycache__/`、`tests/`
- **命令**: `for f in *; do if [ -L "$f" ] && ! [ -e "$(readlink "$f")" ]; then unlink "$f"; fi; done`

### 2. 清空 cron.db 废弃 job (`~/.cron-service/cron.db`)

- **结果**: 完成。20 条 job 全部删除（数据库 VACUUM + WAL 清理）
- **保留 job**: 无。所有 job 脚本均不可达
- **说明**: x2-backup-brain 保留为独立脚本，未来通过 Task Center 重新注册

### 3. 清理 crontab 断裂条目

- **结果**: 完成。从 6 条精简到 2 条
- **保留条目**:
  - `x2-backup-brain` (每天 3:30)
  - `omo-state-sync` (每 6 小时)
- **删除条目**: `x2-freshness-cron`（断裂）、`x2-health-report`（断裂）、`x2-retrospect`（断裂）、`ops-sync-connectors`（断裂）

### 4. 卸载废弃 launchd plist

- **结果**: 无需操作。`com.forge.watchdog` 和 `com.ecos.dashboard` 的 plist 已归档至 `~/.hermes/archived-plists/`，未在 launchd 中注册
- **仍运行的 Hermes 服务**: `ai.hermes.gateway`（已崩溃 -1）、`com.sharedbrain.bos`（status 127）、`com.knowledgebase.gbrain-index`（status 2）——未在本次清理范围

## 遗留事项

| 事项 | 优先级 | 说明 |
|------|--------|------|
| 重写 `scheduled-tasks-audit.py` | 低 | 去除硬编码，动态探测项目分类 |
| 建设 Task Center | 高 | Phase 4 Wave 2-3：统一 5 类任务的管理与调度 |
| arcnode 规范推广 | 中 | 新架构描述系统已在 `~/.hermes/scripts/arcnode/` 中存在 |

## 未来架构方向

根据 [../design/MASTER-BLUEPRINT.md](../design/MASTER-BLUEPRINT.md) 和 Task Center 设计方案（`~/.hermes/scripts/arcnode/schema.py`），后续采用**双 SSOT 架构**：

1. **`tasks/` 治理 SSOT** — 14 字段 YAML，review→done 流程，适合有状态治理
2. **`task-center/` 调度 SSOT** — registry.yaml 管理 5 类任务（cron/once/longrun/webhook/event）

当前保留的 2 条存活任务（x2-backup-brain、omo-state-sync）将在 Task Center MVP 完成后迁移至此新架构。

---

*记录时间: 2026-05-31*
