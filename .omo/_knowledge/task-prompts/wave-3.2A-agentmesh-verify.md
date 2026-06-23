---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 3.2.A — AgentMesh 链路验证

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Wave 3.1.B) | 预估: 1.5h

## 一、目标

验证系统最大的模块（agentmesh 115K LOC）的基本可用性：编译通过、CLI 可用、WorkspaceMCPClient → Agora 链路可达。

## 二、范围

| 验证项 | 说明 | 验收 |
|--------|------|------|
| 编译 | `bun run build` 0 errors | ✅ |
| CLI | `agentmesh --help` 有输出 | ✅ |
| WorkspaceMCPClient | toolkit 能通过 agora 发现 minerva | ✅ |
| Model-Orchestrator | 至少 1 个 provider 可加载 | ✅ |

## 三、不包含

- 完整的运行测试（149 测试跑通 — 那是可选扩展）
- 与 agentmesh 深度集成（那是后续工作）
- DSL 编译器测试

## 四、依赖

- **前置**: Phase 2 minerva 持久化已完成（MCPClient 需要目标服务）
- **确认命令**: `bun --version` >= 1.3

## 五、执行步骤

### Step 1: 编译验证

```bash
cd ~/Workspace/agentmesh
bun install 2>&1 | tail -3
bun run build 2>&1 | tail -5
# 检查 dist/ 目录是否有产出
ls packages/*/dist/ 2>/dev/null
```

### Step 2: CLI 测试

```bash
bun run packages/cli/src/index.ts --help 2>&1 | head -10
# 或
node packages/cli/dist/index.js --help 2>&1 | head -10
```

### Step 3: WorkspaceMCPClient 链路

```python
# 通过 toolkit 连接 agora
cd ~/Workspace/agentmesh
# 查找 WorkspaceMCPClient 入口
grep -rn 'WorkspaceMCPClient' packages/toolkit/src/ | head -5
# 运行集成测试
bun test --filter="MCPClient" 2>&1 | tail -10
```

### Step 4: 标记状态

无论结果如何，在 README 和 AGENTS.md 中记录验证结论。

## 六、输出

| 文件 | 操作 |
|------|------|
| `agentmesh/STATUS.md` | 新增，记录验证结论 |
| `AGENTS.md` | 更新 agentmesh 状态 |
| `.omo/TASK_POOL.md` | T048-T050 → done |

## 七、→ 下一个 Wave

与 Wave 3.2.A 并行的是 **Wave 3.2.B (废弃清理)**，两者无依赖关系。
