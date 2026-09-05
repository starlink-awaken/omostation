---
schema_version: standard/v1
type: ssot
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-05
---

# 文档保鲜 SOP (Docs Freshness SOP)

> 本文档定义了 omostation 工作区中所有文档保鲜（freshness）的规则、检查工具、触发方式和常见故障修复。
> 纯文档规范，不涉及 gate/脚本修改。

---

## 1. Frontmatter 必备字段

所有属于 SSOT 文档体系的 Markdown 文件（`docs/`、`.omo/standards/`、`.omo/_knowledge/decisions/`、`bin/README.md`）**必须**包含以下 YAML frontmatter 字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | 文档类型版本（如 `ssot`、`standard/v1`、`retrospective/v1`） |
| `type` | string | 是 | 文档类别：`ssot` / `retro` / `adr` / `plan` / `report` / `spec` / `sop` |
| `status` | string | 是 | 生命周期状态：`active` / `archived` / `draft` |
| `lifecycle` | string | 是 | 交付合约：`contract` / `advisory` / `ephemeral` |
| `owner` | string | 是 | 责任人/团队（如 `governance-team`、`xiamingxing`） |
| `last-reviewed` | date | 是 | **最后审核日期** `YYYY-MM-DD`，保鲜检测的唯一时间锚点 |

### 不同文档类型的额外字段

| 类型 | 额外必填字段 |
|------|-------------|
| `adr` | `id: ADR-NNNN`（由 `adr-frontmatter-backfill.py` 维护） |
| `retro` | `bet_id`（关联回顾的 BET） |
| `plan` | `scope`（计划覆盖范围） |
| `spec` | `version`（规范版本号） |

### 最后审核日期 (last-reviewed) 规则

- **新建文档**: `last-reviewed` 设为创建当天
- **文档修改**: `last-reviewed` **必须**同步更新为修改当天
- **仅审阅（未改内容）**: `last-reviewed` 可以更新为审阅当天（审阅本身也是保鲜行为）
- **保鲜阈值**: 默认 **30 天**未更新即视为 stale（可通过 X2 规则覆盖）

---

## 2. 保鲜检查工具一览

工作区有多个工具检测文档新鲜度，各有侧重：

### 2.1 `anti-corruption.py` — 文档过期检测（CI 级）

```bash
# 查看报告
python3 bin/gac/anti-corruption.py

# JSON 输出
python3 bin/gac/anti-corruption.py --json

# 强制模式：有违规则 exit 1（CI 阻断用）
python3 bin/gac/anti-corruption.py --enforce
```

- **检查范围**: `docs/` 下所有 `.md` 文件
- **保鲜规则**: `last-reviewed` > 30 天 → stale
- **用途**: CI 级防腐检查，三类腐败之一

### 2.2 `x2-freshness-check.py` — X2 规则驱动保鲜

```bash
# 默认检查
python3 bin/gac/x2-freshness-check.py

# JSON 输出
python3 bin/gac/x2-freshness-check.py --json

# 覆盖阈值天数
python3 bin/gac/x2-freshness-check.py --days 14
```

- **数据源**: `.omo/_truth/x2-freshness-rules.yaml`
- **每条规则**: `target`（路径/glob）+ `threshold_days` + `action`（warn/escalate/error）
- **用途**: 细粒度保鲜策略，可按文件/目录单独设阈值

### 2.3 `meta-doctor.py` — 治理机制活性巡检

```bash
python3 bin/gac/meta-doctor.py --workspace . --json
```

- **M1 心跳**: 检查关键状态投影文件的 `generated_at`/`last_scan` 是否超 SLA
- **M2 引用活性**: cron/launchd 登记的可执行目标路径是否存在
- **用途**: 元治理层保鲜（治理机制自身的活性检测）

### 2.4 `adr-drift-check.py` — ADR 漂移检测

```bash
python3 bin/adr/adr-drift-check.py
```

- **检查范围**: `.omo/_knowledge/decisions/` 下所有 ADR
- **保鲜规则**: ADR frontmatter `status` / `last-reviewed` 状态
- **用途**: ADR 生命周期保鲜

### 2.5 `staleness-check.py` — KB 知识库陈旧检查

```bash
python3 bin/kb/staleness-check.py
```

- **检查范围**: 知识库文件
- **保鲜规则**: `last-reviewed` > 90 天或缺失
- **用途**: 知识库文档保鲜

### 2.6 `adr-coverage.py` — ADR 完整性检查

```bash
python3 bin/adr/adr-coverage.py
```

- **检查范围**: ADR frontmatter 完整性
- **必填字段**: `status`, `lifecycle`, `owner`, `last-reviewed`
- **用途**: 确保所有 ADR frontmatter 完整

---

## 3. `--check` vs `--strict` 差异

大多数检查工具支持两种模式：

| 模式 | 行为 | 退出码 | 用途 |
|------|------|--------|------|
| **默认（report 模式）** | 输出检查报告，不阻断 | 恒 0 | 日常巡检、手动审查 |
| **`--check`**（部分工具） | 验证条件，不修改文件 | 0=通过, 1=不通过 | CI 门禁、PR 前验证 |
| **`--strict`** | 更严格：任何预期变更都视为失败 | 0=无需变更, 1=有变更 | 合并阻断、清洁分支验证 |

### 典型使用场景

```bash
# 日常巡检（只看报告）
python3 bin/gac/anti-corruption.py

# CI 门禁（PR 检查，不修改文件）
python3 bin/gac/anti-corruption.py --enforce

# ADR frontmatter 严格检查（CI 阻断）
python3 bin/adr/adr-frontmatter-backfill.py --strict

# ADR frontmatter 预览（不修改）
python3 bin/adr/adr-frontmatter-backfill.py --dry-run
```

---

## 4. 触发 Workflow

### 4.1 常规保鲜巡检

```bash
# 收敛脉搏周报（含文档保鲜检查）
uv run --with pyyaml python bin/agent-workflow.py start convergence-pulse-weekly \
  --profile governance-agent \
  --objective "文档保鲜巡检"

# 文档消费者审计（含 bridge shell sha 核验）
uv run --with pyyaml python bin/agent-workflow.py start documents-consumer-audit-weekly \
  --profile governance-agent \
  --objective "文档消费者审计"
```

### 4.2 单文件保鲜修复

```bash
# 1. 发现 stale 文件
python3 bin/gac/anti-corruption.py --json | jq '.docs.stale'

# 2. 审阅并更新 last-reviewed
vim <stale-file>  # 更新 frontmatter 中的 last-reviewed

# 3. 验证修复
python3 bin/gac/anti-corruption.py --enforce
```

### 4.3 ADR 保鲜

```bash
# 回填缺失的 frontmatter id
python3 bin/adr/adr-frontmatter-backfill.py --dry-run  # 预览
python3 bin/adr/adr-frontmatter-backfill.py             # 执行

# 检查 ADR 完整性
python3 bin/adr/adr-coverage.py
```

### 4.4 治理机制自身保鲜

```bash
# 检查治理机制活性（M1 心跳 + M2 引用）
python3 bin/gac/meta-doctor.py --workspace . --json

# X2 细粒度保鲜
python3 bin/gac/x2-freshness-check.py --json
```

---

## 5. 常见失败修复

### 5.1 `anti-corruption.py --enforce` 失败：文档过期

**症状**: `docs.stale_count > 0`，exit 1

**修复**:
1. 找出 stale 文件：`python3 bin/gac/anti-corruption.py --json | jq '.docs.stale[]'`
2. 逐个打开，审阅内容是否仍然准确
3. 更新 `last-reviewed` 为今天日期
4. 如内容已过期，先修正内容再更新日期
5. 重新验证：`python3 bin/gac/anti-corruption.py --enforce`

### 5.2 `adr-frontmatter-backfill.py --strict` 失败

**症状**: `changed > 0`，exit 1（说明有 ADR 缺少 `id` 字段）

**修复**:
1. 预览影响：`python3 bin/adr/adr-frontmatter-backfill.py --dry-run --json`
2. 执行回填：`python3 bin/adr/adr-frontmatter-backfill.py`
3. 验证：`python3 bin/adr/adr-frontmatter-backfill.py --strict`

### 5.3 `x2-freshness-check.py` 报 fail

**症状**: 某规则触发 `action: error`

**修复**:
1. 查看具体规则：`cat .omo/_truth/x2-freshness-rules.yaml`
2. 检查 target 路径文件是否过期
3. 更新对应文件的 `last-reviewed`
4. 如规则阈值不合理，修改 `x2-freshness-rules.yaml` 中的 `threshold_days`

### 5.4 `meta-doctor.py` M1 心跳失活

**症状**: 某投影文件的 `generated_at`/`last_scan` 超 SLA

**修复**:
1. 确认失活文件：查看 JSON 输出中的 `m1.violations`
2. 重新运行对应投影生成脚本
3. 验证时间戳已更新

### 5.5 Frontmatter 缺少必填字段

**症状**: `adr-coverage.py` 报告 frontmatter 不完整

**修复**:
1. 查看缺失字段：`python3 bin/adr/adr-coverage.py`
2. 手动补齐必填字段（`status`, `lifecycle`, `owner`, `last-reviewed`）
3. 对于 ADR 类型还需 `id: ADR-NNNN`

### 5.6 `last-reviewed` 日期格式错误

**症状**: 保鲜检查工具跳过某文件

**原因**: `last-reviewed` 值不是 `YYYY-MM-DD` 格式

**修复**:
1. 检查 frontmatter 中 `last-reviewed` 的值
2. 确保格式为 `YYYY-MM-DD`（如 `2026-09-05`）
3. 注意 YAML 中日期不要加引号（加引号会被当作字符串而非日期）

---

## 6. 保鲜节奏

| 频率 | 检查项 | 负责人 |
|------|--------|--------|
| **每次 PR** | `anti-corruption.py --enforce` | CI |
| **每日** | `meta-doctor.py` M1 心跳 | 自动化 |
| **每周** | `convergence-pulse-weekly` workflow | governance-agent |
| **每月** | 全量 `x2-freshness-check.py` | governance-team |
| **每季** | `adr-coverage.py` + `staleness-check.py` 全量扫描 | governance-team |

---

## 7. 参考

- **SSOT 正交契约**: `.omo/standards/doc-ssot-contract.md`
- **X2 保鲜规则**: `.omo/_truth/x2-freshness-rules.yaml`
- **ADR 决策目录**: `.omo/_knowledge/decisions/`
- **反腐败 CI**: `bin/gac/anti-corruption.py`
- **元治理巡检**: `bin/gac/meta-doctor.py`
