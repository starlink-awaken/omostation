---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T6-19
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T6-19 Agent 感知覆盖率提升 — Skills/Workflows 可发现

## 1. 目标

让任何新进的 AI agent 都能在 ≤ 30 秒内发现并正确调用现有 skills/workflows/MCP/BOS 能力。

## 2. In scope

1. **`.agents/skills/INDEX.md` 同步**: 自动生成, 每次 build 后真实计数 (当前 40 skills)
2. **AGENTS.md 能力发现段落**: 修正硬编码数字, 改为动态引用或 generator 脚本; 增加 MCP/BOS URI 完整性检查入口
3. **Workflow 注册验证**: `.omo/_truth/registry/agent-workflows/INDEX.md` 反映当前 31 个 workflows
4. **MCP/BOS URI 完整性检查脚本**: `bin/gac/check-mcp-bos-uri-completeness.py`, 校验所有 registered tools 的 server_name/tool_name 非空、URI 唯一、可达
5. **生成器可重建**: 三类 INDEX (skills/workflows/capability-registry) 都由 generator 派生, 不允许手工维护

## 3. Out of scope

- 不重写任何已有 skill / workflow 内容 (只校验完整性)
- 不修改 BOS URI schema
- 不创建新的 SSOT 索引系统
- 不集成到 Cockpit UI

## 4. 验收

1. `test -f .agents/skills/INDEX.md` → exit 0
2. INDEX.md 内 skills 数量 = 实际 `find .agents/skills -name SKILL.md | wc -l`
3. AGENTS.md 能力发现段落存在, 不含过期硬编码数字
4. `bin/gac/check-mcp-bos-uri-completeness.py` 运行 exit 0 (无 missing/duplicate)
5. workflow registry INDEX.md 内 workflows 数量 = 实际 `find ... -name "*.yaml" | wc -l`
