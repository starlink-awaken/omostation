# 架构升级优化方案 v4

> 基于 4+1+3 全映射 (2026-05-28)
> 遵循 MECH-05 Wave 分解模型

---

## TL;DR

**目标**: 补齐 6 个 🟡 Medium 差距，打通 L3 协作层核心链路
**总工时**: ~12h（Wave 1-3 并行，Wave 4 串行）
**关键路径**: T2 → T3（collab→agentmesh 集成）

## Wave 架构

```
Wave 1 (完全并行, 4 任务, ~4h):
├── T1: gstack orchestrator → Interceptor backend    [2h] P0
├── T2: KOS collab → agentmesh MCP 调用              [3h] L3 ★
├── T3: KnowledgeLinks → KOS MCP 消费                [1h] L4
└── T4: SharedBrain DB 自动备份脚本                   [0.5h] 运维

Wave 2 (依赖 T2, 2 任务, ~3h):
├── T5: agentmesh → KOS collab 状态回写              [2h] L3
└── T6: PipelineTracer → collab 关联                 [1h] L3

Wave 3 (无依赖, 2 任务, ~2h):
├── T7: X2 freshness cron 加入 crontab                [0.5h] X2
├── T8: Agent deep Read Budget 自动化                 [1.5h] 平台

Wave 4 (最终验证):
└── F1-F4: 通断测试 + 集成验证 + 质量审查 + 文档同步
```

---

## TODOs

- [ ] 1. gstack orchestrator → Interceptor backend 对接

  **What to do**:
  - 读取 gstack/agents/ 中的 orchestrator 定义（如 make-pdf）
  - 读取 gstack/src/backends.ts（我们的接口定义）
  - 在 backends.ts 中实现 `InterceptorBackend` 类（实现 BrowserBackend 接口）
  - Interceptor 调用方式：使用现有的 `open_url`/`click`/`type` 等 compound command
  - 更新 gstack/orchestrators-index.md 标注每个 orchestrator 可用的 backend

  **Must NOT do**:
  - 不要修改 Interceptor skill 本身
  - 不要实现所有 20 个 orchestrator（只做接口层）

  **Acceptance criteria**:
  - [ ] InterceptorBackend 实现 execute()/batch()/screenshot()
  - [ ] 至少 1 个 orchestrator 可通过 Interceptor 执行
  - [ ] orchestrators-index.md 已更新

  **Agent**: Visual-engineering | Wave 1 | Parallel with T2,T3,T4

- [ ] 2. KOS collab → agentmesh MCP 调用（打通 L3 链路）

  **What to do**:
  - 读取 KOS kos/collab/api.py 中的 `execute_task(task_id)` 或 `create_task()` 返回后的下一步逻辑
  - 在 collab/api.py 中添加 MCP 客户端调用（`mcp.connect("agentmesh")` 或 httpx POST）
  - 调用 agentmesh Gateway 的 POST /v1/tasks（用已配置的 API_KEY）
  - 将 agentmesh 返回的 task_id 写入 KOS collab 的 TaskObject.artifacts 中
  - 使用环境变量 `AGENTMESH_API_URL` 和 `API_KEY` 配置连接
  - 失败时不影响 collab 本身（try/except，记 warning 日志）

  **Must NOT do**:
  - 不要修改 agentmesh 的 API
  - 不要在 collab 中硬编码 agentmesh URL
  - 不要阻塞 collab 的正常 CRUD

  **QA**:
  ```
  Scenario: collab 创建任务后调用 agentmesh
    Tool: Python
    Steps:
      1. 设置 AGENTMESH_API_URL=http://localhost:3000
      2. 调用 collab create_task()
      3. 验证 artifacts 中包含 agentmesh_task_id
    Expected: 任务创建成功，artifacts 非空
  ```

  **Agent**: deep (加 Read Budget) | Wave 1 | Parallel with T1,T3,T4

- [ ] 3. KnowledgeLinks → KOS MCP 消费

  **What to do**:
  - 读取 kos/domain/self/knowledge_links.yaml（已创建 25 条目）
  - 在 kos/kos/self/api.py 中，给 each `get_profile()` 或 `get_cognitive_frameworks()` 方法加一个步骤：
  - 读取 knowledge_links.yaml, 匹配当前 cognitive_framework 名称
  - 如果有匹配的 link，追加到返回结果中的 `_knowledge_links` 字段
  - 不影响现有返回值结构（只追加一个只读字段）

  **Must NOT do**:
  - 不要改现有返回值 schema
  - 不要引入新依赖

  **QA**:
  ```
  Scenario: cognitive_frameworks 返回包含知识链接
    Tool: Python
    Steps:
      1. 调用 get_cognitive_frameworks()
      2. 检查返回中是否包含 _knowledge_links
    Expected: 包含 1+ 个链接
  ```

  **Agent**: quick | Wave 1 | Parallel with T1,T2,T4

- [ ] 4. SharedBrain DB 自动备份脚本

  **What to do**:
  - 创建 ~/.hermes/scripts/x2-backup-brain
  - Python3 executable
  - 备份路径: SharedBrain/data/db/ 下的所有 SQLite 文件
  - 备份目标: SharedBrain/data/db/backup/{YYYYMMDD}/
  - 使用 sqlite3 .backup 命令（在线安全备份）
  - 保留最近 30 天的备份，更早的自动清理
  - 运行完成打印摘要: "Backed up N files, cleaned M old backups"
  - 注册到 INDEX.md

  **Must NOT do**:
  - 不要修改 SharedBrain 代码
  - 不要复制正在写入的数据库（使用 .backup 命令）

  **Agent**: quick | Wave 1 | Parallel with T1,T2,T3

- [ ] 5. agentmesh → KOS collab 状态回写

  **What to do**:
  - 在 agentmesh Gateway 添加一个 webhook 回调机制
  - 当任务完成/失败时，POST 回调到 collab 的 MCP 地址
  - 在 KOS collab 添加 `update_task_status(agentmesh_task_id, status, output)` 端点
  - 配置方式：`TASK_CALLBACK_URL` 环境变量

  **Must NOT do**:
  - 不要改 collab 现有 TaskObject schema
  - 回写失败不阻塞 agentmesh

  **Agent**: quick | Wave 2 | Blocked by T2

- [ ] 6. PipelineTracer → collab 关联

  **What to do**:
  - 在 PipelineTracer 的 `completeStep()` 和 `failStep()` 方法中增加回调钩子
  - 当步骤状态变化时，如果有关联的 collab task_id，POST 到 collab
  - 关联方式: `provenance.collab_task_id` 字段（在 PipelineTracer 记录中）

  **Agent**: quick | Wave 2 | Blocked by T2

- [ ] 7. X2 freshness cron 加入 crontab

  **What to do**:
  - 检查当前 crontab：crontab -l 2>/dev/null
  - 添加每日凌晨 3 点运行 freshness cron：
    `0 3 * * * cd ~ && python3 ~/.hermes/scripts/x2-freshness-cron --dry-run >> ~/.hermes/logs/x2-freshness.log 2>&1`
  - 添加每日凌晨 3:30 运行 backup：
    `30 3 * * * python3 ~/.hermes/scripts/x2-backup-brain >> ~/.hermes/logs/x2-backup.log 2>&1`
  - 创建 `~/.hermes/logs/` 目录

  **Agent**: quick | Wave 3 | No dependencies

- [ ] 8. Agent deep Read Budget 自动化

  **What to do**:
  - 创建 `~/.hermes/scripts/agent-read-budget` — 一个可被 task prompt 引用的合约
  - 内容：Read Budget 机制（来自 .omo/summaries/agent-task-contract.md）
  - 实质改动：在所有涉及 `deep`/`unspecified-high` 类别的 Task Prompt 中，自动在 Prompt 末尾追加 Read Budget 段落
  - 验证方式：用一个已知会卡死的任务测试，确认 5 次 read 后强制 write

  **Agent**: quick | Wave 3 | No dependencies

---

## 最终验证 (F1-F4)

- [ ] F1. 全链路集成测试：collab create → agentmesh execute → collab status update → PipelineTracer trace → complete
- [ ] F2. 代码质量审查 (tsc/pytest/lint)
- [ ] F3. backup cron + freshness cron 运行验证
- [ ] F4. Read Budget 压力测试（deep agent 验证）

## Commit Strategy

- T1: `feat(gstack): add Interceptor backend`
- T2: `feat(kos): connect collab to agentmesh via MCP`  
- T3: `feat(kos): wire knowledge_links to self MCP`
- T4: `feat(ops): add SharedBrain DB backup script`
- T5: `feat(agentmesh): add task callback to collab`
- T6: `feat(obs): link PipelineTracer to collab`
- T7: `feat(ops): schedule freshness + backup crons`
- T8: `feat(ops): auto-attach Read Budget to deep tasks`
