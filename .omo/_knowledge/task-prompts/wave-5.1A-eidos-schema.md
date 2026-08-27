---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 5.1.A — Eidos Schema 定义

> 类型: P9 → P8 Task Prompt | 状态: backlog | 预估: 105min
> Phase: 5 → 5.1.A | 负责人: prometheus | 日期: Day 1

## 一、目标

在Eidos中定义4个新Schema（identity-role, value-principle, consensus, task-object），并在registry中注册。同时创建epoch-life schema确保本次实施的组件自带`--json`输出和路径无关约束。

## 二、范围

### 文件清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `eidos/schemas/identity-role.schema.json` | 新建 | 角色画像Schema：role_id, name, priority, values, time_window, communication_style |
| `eidos/schemas/value-principle.schema.json` | 新建 | 价值原则Schema：name, weight, source_axiom, conflict_resolution, version |
| `eidos/schemas/consensus.schema.json` | 新建 | 共识Schema：entity_id, level(1/2/3), agreed_by, agreement, confirmed_at, expires_at |
| `eidos/schemas/task-object.schema.json` | 新建 | 任务协作Schema：id, title, goal, subtasks[], artifacts[], progress, status, resources |
| `eidos/schemas/registry.json` | 追加 | 注册4个新Schema+版本号 |
| `eidos/schemas/epoch-life.schema.json` | 新建 | 组件约束Schema：所有组件必须有`--json`输出和路径无关约束 |

### 详细Schema定义

见09-实施方案-细化方案.md Day 1部分:

- identity-role: 包含role_id( pattern: ^role:[a-z-]+$ ), name, priority(1-10), values[], time_window, communication_style, tags[]
- value-principle: 包含name, weight(0-1), source_axiom, conflict_resolution, version(int), status(active|superseded|archived)
- consensus: 包含consensus_id, entity_id, level(1|2|3), agreed_by[], agreement, source_session, confirmed_at, expires_at, status
- task-object: 包含id, title, goal, creator, visibility_scope, subtasks[], artifacts[], progress(0-100), status, timeline[], resource_usage
- epoch-life: 包含json_output(boolean), path_free(boolean), half_life_days(int)

## 三、验收标准

```
☐ eidos/schemas/下新增5个JSON Schema文件
☐ eidos/schemas/registry.json 已注册新Schema
☐ workspace contracts validate 全部通过
☐ workspace contracts list 显示新条目
```

## 四、依赖

- **前置**: Eidos项目已存在（`~/Workspace/eidos/`）
- **确认命令**: `ls ~/Workspace/eidos/schemas/` 确认目录存在

## 五、执行步骤

### Step 1: 创建 identity-role.schema.json

```bash
cd ~/Workspace/eidos
cat > schemas/identity-role.schema.json << 'EOF'
{...完整的JSON Schema...}
EOF
```

详细内容见09-实施方案-细化方案.md的Day 1部分。

### Step 2: 创建 value-principle.schema.json

同上，使用细化方案中的完整定义。

### Step 3: 创建 consensus.schema.json

同上，使用细化方案中的完整定义。

### Step 4: 创建 task-object.schema.json

同上，使用细化方案中的完整定义。

### Step 5: 创建 epoch-life.schema.json

根据RETRO-COMPLETE经验（路径硬编码教训、`--json`标准化经验）定义约束schema。

### Step 6: 更新 registry.json

追加5个新Schema到registry.json的schemas数组。

### Step 7: 验证

```bash
cd ~/Workspace/Workspace
python3 -m wksp contracts validate
python3 -m wksp contracts list | grep -E "identity-role|value-principle|consensus|task-object|epoch-life"
```

## 六、输出

| 文件 | 操作 |
|------|------|
| `eidos/schemas/identity-role.schema.json` | 新建，v1 |
| `eidos/schemas/value-principle.schema.json` | 新建，v1 |
| `eidos/schemas/consensus.schema.json` | 新建，v1 |
| `eidos/schemas/task-object.schema.json` | 新建，v1 |
| `eidos/schemas/epoch-life.schema.json` | 新建，v1 |
| `eidos/schemas/registry.json` | 追加5条记录 |
| `.omo/TASK_POOL.md` | T063-T065 → done |
| `.omo/STATE.md` | 更新Wave 5.1.A进度 |

## 七、→ 下一个Wave

完成后触发 **Wave 5.1.B (KOS EntityType 扩展)**。
