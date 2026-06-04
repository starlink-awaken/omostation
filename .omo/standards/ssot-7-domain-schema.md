# SSOT 7 Domain Schema — Full Execution Governance Standard

> 日期: 2026-05-30 | 版本: v1.0 | 状态: active
> 关联: `../_knowledge/design/MASTER-BLUEPRINT.md` §VIII, `.omo/tasks/`, `goals/current.yaml`, `state/system.yaml`, `convergence.yaml`, KOS index
> 适用范围: Phase 2 full_execution 下所有 SSOT domain 的注册、读写、同步、审计

---

## 1. 7 Domains 总览

| # | 域 | 图标 | 职责 | Owner | Source of Truth | Write Policy | Read Policy |
|---|-----|------|------|-------|----------------|-------------|------------|
| 1 | **Knowledge** | 🧠 | 个人知识库（Obsidian vault、AI papers、KEMS 方法论） | `@self` | Obsidian vault (`~/Documents/Obsidian/`) | L1: 增量同步；L2: 全量重建 | L0: 搜索/查询 |
| 2 | **Work** | 💼 | 工作文档（卫健委、国转中心、legal、templates） | `@self` | `~/Documents/工作文档/` | L1: 增量同步 | L0: 搜索/查询 |
| 3 | **Family** | 👨‍👩‍👧‍👦 | 家庭信息（成员、健康、教育、资产） | `@self` | iCloud FamilyShared | L1: 仅通过 coordinator | L0: 本地只读 |
| 4 | **AI** | 🤖 | AI 能力（462GB models、agents、tools、pipelines） | `governance` | AROOL_REGISTRY + Agora registry | L1: 工具注册；L2: 模型变更 | L0: 发现/查询 |
| 5 | **System** | ⚙️ | 系统基础设施（4+1+3+1 架构、`.omo` 治理、ops） | `governance` | `.omo/` + Hermes + Docker | L1: 治理写入；L2: 架构变更 | L0: 状态查询 |
| 6 | **Data** | 📁 | 文件与数据（iCloud、SharedDisk、Desktop、sync） | `@self` | filesystem + iCloud + SharedDisk | L1: 增量同步 | L0: 文件列表/读取 |
| 7 | **Media** | 🎬 | 媒体文件（photos、videos、music、albums） | `@self` | SharedDisk | L1: 增量同步 | L0: 浏览/播放 |

> **sensitive capabilities remain blocked**: Apple / WeChat / Family OS / SMB / media indexing / autonomous self-healing / destructive backup-restore 不在此 schema 范围内。

---

## 2. 每个 Domain 与治理文件的关系

### 2.1 与 `.omo/tasks/` 的关系

| Domain | 任务来源 | 可写 | 说明 |
|--------|----------|:----:|------|
| Knowledge | KOS index 自动发现 | ❌ 只读 | 任务不直接管理 knowledge domain |
| Work | KOS index 自动发现 | ❌ 只读 | 同上 |
| Family | 暂未入 KOS | ❌ 只读 | blocked until Safe Mesh |
| AI | `M2.3-OPERATION-LEVEL-ROLLOUT-PLAN` | ✅ 可写 | governance agent 可注册 AI 工具 |
| System | `.omo/tasks/active/*.yaml` | ✅ 通过 coordinator | 任务 SSOT 的唯一写入口 |
| Data | KOS index 自动发现 | ❌ 只读 | 由 indexer 管理 |
| Media | 暂未入 KOS | ❌ 只读 | blocked until Safe Mesh |

### 2.2 与 `.omo/state/system.yaml` 的关系

- **AI domain**: `active_agents`, `idle_agents`, `dead_agents` 由 Agent Registry 更新
- **System domain**: `current_phase`, `phase_status`, `health_score`, `last_go_nogo` 由 aggregator 更新
- **所有 domain**: `governance_consistency` 是跨域聚合指标
- agent 禁止直接写 `system.yaml` — 必须通过 aggregator 或人工校准

### 2.3 与 `.omo/goals/current.yaml` 的关系

- **System domain**: `goals` 列表定义当前 Phase 目标，governance agent 可更新 progress
- **Knowledge domain**: KOS baseline 修复是 G2.0 目标
- 非 governance agent 禁止修改 `goals/current.yaml`

### 2.4 与 `convergence.yaml` 的关系

- **System domain**: `projects` 列表、`phase1_status`、`phase2_entry` 由 governance 维护
- agent 禁止直接写 `convergence.yaml` — 必须通过 coordinator 统一同步

### 2.5 与 KOS index 的关系

| Domain | KOS 索引状态 | Zone | 文档数 |
|--------|:-----------:|:----:|:------:|
| Knowledge | ✅ 已索引 | workspace_root | 8 |
| Work | ✅ 已索引 | workspace_root | 同知识域 |
| Family | ❌ 未索引 | — | — |
| AI | ✅ 已索引 | kairon, agentmesh, gbrain | 1886+38+506 |
| System | ✅ 已索引 | omo, sharedbrain | 179+4710 |
| Data | ✅ 部分索引 | workspace_root | 同根目录 |
| Media | ❌ 未索引 | — | — |

KOS baseline document count: **7327** (captured 2026-05-30)
Known document retrieval: **10/10**

---

## 3. 核心字段与状态枚举

### 3.1 通用字段（所有 domain 共享）

```yaml
domain: string          # 域名: knowledge | work | family | ai | system | data | media
domain_id: string       # 唯一 ID, 格式: "{domain}.{subdomain}" (e.g. "knowledge.personal")
version: string         # schema 版本号 (semver)
maintainer: string      # 维护者标识: "@self" | "governance" | "coordinator"
source_of_truth: string # 权威数据源路径/标识
sync_mode: enum         # pull | push | coordinator_only
status: enum            # registered | active | degraded | blocked | archived
```

### 3.2 状态枚举

```yaml
DomainStatus:
  - registered    # 已注册 schema，尚未同步数据
  - active        # 正常运行，数据可查询
  - degraded      # 部分数据不可用（如 KOS count drop >10%）
  - blocked       # 被 gate 阻止（如 sensitive capabilities）
  - archived      # 已归档，不再使用

AgentStatus:
  - active        # heartbeat < 60s
  - stale         # heartbeat 60-180s
  - zombie        # heartbeat > 180s
  - dead          # zombie > 24h

TaskStatus:
  - candidate     # 来自计划但尚未通过入场门禁
  - pending       # 已通过入场门禁，可被 agent 认领
  - in_progress   # 正在执行
  - review        # 实现完成但证据待验收
  - done          # 已完成，含 evidence
  - blocked       # 被阻塞
  - failed        # 执行失败
```

### 3.3 ID 命名规则

```
Domain ID:     "{domain}.{subdomain}"                    e.g. "knowledge.personal", "system.infrastructure"
Task ID:       "M{milestone}-{DOMAIN}-{SHORT_DESC}"      e.g. "M2.3-KOS-BASELINE-DRIFT-MONITOR"
Agent ID:      "{type}-{name}"                            e.g. "research-minerva-01", "governance-architect"
Schema field:  snake_case                                  e.g. "domain_id", "source_of_truth"
```

---

## 4. Agent 写入规则

### 4.1 文件读写权限矩阵

| 文件/目录 | 可读 | 可写 | 写者 | 同步方式 |
|-----------|:----:|:----:|------|----------|
| `.omo/tasks/active/*.yaml` | ✅ 全部 | ✅ 认领的任务 | assigned agent | 直接写 |
| `.omo/tasks/done/*.yaml` | ✅ 全部 | ❌ 只读 | — | 由 active 迁移 |
| `.omo/tasks/blocked/*.yaml` | ✅ 全部 | ✅ 认领的任务 | assigned agent | 直接写 |
| `.omo/state/system.yaml` | ✅ 全部 | ❌ 只读 | aggregator 独写 | 必须通过 coordinator |
| `.omo/goals/current.yaml` | ✅ 全部 | ❌ 只读 | governance 独写 | 必须通过 coordinator |
| `convergence.yaml` | ✅ 全部 | ❌ 只读 | governance 独写 | 必须通过 coordinator |
| `.omo/standards/*.md` | ✅ 全部 | ✅ 审阅后 | governance agent | coordinator 收口 |
| `.omo/summaries/*.md` | ✅ 全部 | ✅ 任何 agent | 写后告知 coordinator | 独立写 |
| `projects/kairon/packages/*/` | ✅ 全部 | ✅ 代码变更 | assigned developer | PR/CI |
| KOS index | ✅ 查询 | ❌ 只读通过 MCP | indexer 独写 | L2 human approval |
| `~/.omostation/audit/` | ❌ 专有 | ✅ audit 系统 | auditor 独写 | 追加写 |

### 4.2 Coordinator 同步规则

以下操作**必须**通过 coordinator 统一同步：

1. **任务状态变更**（task YAML 迁移 active→done→blocked）
2. **治理状态更新**（`system.yaml`, `goals/current.yaml`, `convergence.yaml`）
3. **domain schema 变更**（新建/修改 domain schema 文件）
4. **跨 Agent 依赖协调**（Task A 完成触发 Task B 认领）
5. **敏感能力门禁**（任何 blocked capability 的解锁）

以下操作可**独立执行**：

1. 读取任何只读文件
2. 写入自己认领的任务 YAML
3. 写入审计日志（append-only）
4. 读取 KOS index（L0）

---

## 5. Migration / Compatibility

### 5.1 从旧 SSOT（v0.x）迁移

Phase 1 的 ssot 包 (`projects/kairon/packages/ssot/domains/*.yaml`) 已有 7 个 domain 的 schema 骨架文件。当前 schema 文档是对这些骨架的治理层补充，不冲突。

迁移建议：

| 文件 | 状态 | 动作 |
|------|:----:|------|
| `ssot/domains/knowledge.yaml` | ✅ 存在 | 补充 governance 字段 |
| `ssot/domains/work.yaml` | ✅ 存在 | 补充 governance 字段 |
| `ssot/domains/family.yaml` | ✅ 存在 | 保持 blocked |
| `ssot/domains/ai.yaml` | ✅ 存在 | 补充 agent registry 引用 |
| `ssot/domains/system.yaml` | ✅ 存在 | 补充 task SSOT 引用 |
| `ssot/domains/data.yaml` | ✅ 存在 | 补充 sync 策略 |
| `ssot/domains/media.yaml` | ✅ 存在 | 保持 blocked |

### 5.2 KOS Entity 兼容性

现有的 KOS 实体（zone-based）与新 SSOT domain 的映射：

```text
KOS zone         → SSOT domain
──────────────────────────────
workspace_root   → Data, Knowledge (根目录文件)
omo              → System (.omo 治理文件)
kairon           → AI, System (kairon 包代码)
agentmesh        → AI (agentmesh 包代码)
gbrain           → AI (gbrain 包代码)
sharedbrain      → System (SharedBrain 包代码)
```

KOS entity 的 `zone` 和 `canonical_path` 字段可作为 SSOT domain 的 `source_of_truth` 引用。

---

## 6. Validation Checklist

每个 domain 注册前必须通过以下检查：

| # | 检查项 | 通过条件 |
|---|--------|----------|
| 1 | domain name | 是 7 个预定义域之一 |
| 2 | domain_id | 格式 `{domain}.{subdomain}`, 唯一 |
| 3 | source_of_truth | 指向可解析的路径或标识 |
| 4 | write_policy | 明确 L0-L3 级别和审批要求 |
| 5 | read_policy | 明确 L0-L3 级别 |
| 6 | status | 必须是有效枚举值 |
| 7 | sensitive_gate | 如果 blocked，必须有 blocked_by 字段 |
| 8 | KOS mapping | 如果有对应 KOS zone，需记录 zone 名和 count |
| 9 | task_yaml_reference | 如果关联 active task，需有 task_id |
| 10 | coordinator_review | 架构变更必须 coordinator 审阅 |

---

## 7. Sensitive Capabilities 保持 Blocked

以下能力在任何 domain schema 中**禁止**取消 `blocked` 状态，直到 Safe Mesh 操作分级和 Agent Registry heartbeat 完成部署验证：

- Apple 连接器（Calendar, Contacts, Reminders, Notes）
- WeChat 消息连接器
- Family OS 调度（家庭成员设备协同）
- SMB / NAS 文件索引
- 媒体文件全量索引（photos, videos）
- 高自主 Agent 自愈（自动重启、自动回滚）
- 破坏性备份/恢复操作（无 dry-run 门禁）

---

## 8. 文档验证

```yaml
# 验证命令
checklist:
  - "7 domains listed: knowledge, work, family, ai, system, data, media"     ✅
  - "Each domain has: name, owner, source_of_truth, write_policy, read_policy" ✅
  - "Relationships with .omo/tasks, system.yaml, goals.yaml, convergence.yaml" ✅
  - "Agent write rules documented: coord sync vs independent write"           ✅
  - "Sensitive capabilities remain blocked"                                  ✅
  - "KOS mapping documented with baseline 7327"                              ✅
  - "Validation checklist: 10 items"                                         ✅
```

---

*文档版本: v1.0 | 维护者: governance | 同步模式: coordinator_only*
