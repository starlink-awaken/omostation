---
description: "Query the mimocode trajectory database to find repeated manual workflows worth packaging into skills/agents/commands. Read-only SQLite analysis — never modifies the database."
---

# Trajectory Distill Pass — 从历史会话蒸馏可复用工作流

## 1. 定位数据库

```bash
find ~/.local/share/mimocode -name "mimocode.db" 2>/dev/null
```

## 2. 资产盘点

```bash
# 会话/消息/part 数量
sqlite3 ~/.local/share/mimocode/mimocode.db \
  "SELECT COUNT(*) as sessions FROM session; SELECT COUNT(*) as messages FROM message;"

# 已有 skills/agents/commands
ls .agents/skills/ .mimocode/skills/ .mimocode/commands/ 2>/dev/null
```

## 3. 找重复模式

### 3a. 最高频工具使用

```bash
sqlite3 ~/.local/share/mimocode/mimocode.db "
SELECT json_extract(p.data, '$.tool') as tool, COUNT(*) as n
FROM message m JOIN part p ON p.message_id = m.id
WHERE json_extract(m.data, '$.role') = 'assistant'
  AND json_extract(p.data, '$.type') = 'tool'
GROUP BY tool ORDER BY n DESC LIMIT 15;"
```

### 3b. 最高频命令序列

```bash
sqlite3 ~/.local/share/mimocode/mimocode.db "
SELECT SUBSTR(json_extract(p.data, '$.state.input'), 1, 200) as cmd, COUNT(*) as n
FROM message m JOIN part p ON p.message_id = m.id
WHERE json_extract(m.data, '$.role') = 'assistant'
  AND json_extract(p.data, '$.type') = 'tool'
  AND json_extract(p.data, '$.tool') IN ('Bash', 'bash')
GROUP BY cmd ORDER BY n DESC LIMIT 20;"
```

### 3c. 用户重复请求

```bash
sqlite3 ~/.local/share/mimocode/mimocode.db "
SELECT SUBSTR(json_extract(p.data, '$.text'), 1, 200) as text, COUNT(*) as n
FROM message m JOIN part p ON p.message_id = m.id
WHERE json_extract(m.data, '$.role') = 'user'
  AND (json_extract(p.data, '$.text') LIKE '%again%'
    OR json_extract(p.data, '$.text') LIKE '%every time%'
    OR json_extract(p.data, '$.text') LIKE '%like last time%'
    OR json_extract(p.data, '$.text') LIKE '%repeat%'
    OR json_extract(p.data, '$.text') LIKE '%每次%'
    OR json_extract(p.data, '$.text') LIKE '%重复%')
GROUP BY text ORDER BY n DESC LIMIT 10;"
```

### 3d. 跨 session 的模式（用 memory 交叉验证）

```bash
# 在 memory 中搜索 "pattern" / "convention" / "always" / "rule"
# 如果 memory 中记录了某个模式，说明它跨 session 存在
```

## 4. 候选评估

对每个候选模式，检查：

| 维度 | 问题 | 决策 |
|------|------|------|
| 频率 | 出现 5+ 次？ | 低频 → 跳过 |
| 稳定性 | 输入/输出格式一致？ | 不稳定 → 跳过 |
| 已覆盖 | 已有 skill/command/脚本？ | 已覆盖 → 跳过 |
| 复杂度 | 需要 3+ 步骤？ | 太简单 → 跳过 |
| 通用性 | 其他 agent 也能用？ | 太特定 → 跳过 |

## 5. 创建资产

### Skill（知识型）
适合：需要判断力的工作流（如 ecos-test-cycle）

```bash
mkdir -p .agents/skills/<name>
# 写 SKILL.md
```

### Command（执行型）
适合：固定步骤的命令序列（如 omo-review）

```bash
# 写 .mimocode/commands/<name>.md
```

### Agent（角色型）
适合：需要独特身份/视角的工作流（如 laowang-engineer）

```bash
# 写 .claude/agents/<name>.md
```

## 6. 验证

- [ ] 新资产不重复已有功能
- [ ] 触发词/描述准确
- [ ] GaC 检查通过（如适用）
- [ ] 已推送到 git
