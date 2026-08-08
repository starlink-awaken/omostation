# Tasks Registry — 结构化任务注册表

> 替代 system.yaml 中的 orphaned_tasks blob。
> 每个任务有独立 YAML 文件。system.yaml 只保留指针引用。
> **SSOT**: 任务文件在 `tasks/` 下。本文档由验证流程生成，与实际目录保持同步。
> 
> **计数口径**: 与 `omo state sync-tasks` 保持一致，只统计 `tasks/{active,planned,done}/` 顶层 `*.yaml` 文件（不含子目录与草稿）。

## Active Tasks

当前无活跃任务。所有 in-progress 任务通过 `.omo/tasks/planned/` 排队等待认领。

## Planned Tasks (68 个)
| ID | Title | Status |
|----|-------|--------|
| bet-y1q1-t1-00 | 并发写冲突止血 — 共享主树禁写 + PASW 全覆盖 | candidate |
| bet-y1q1-t1-01 | 废除 X3 mtime 交付指标 | candidate |
| bet-y1q1-t1-02 | 子模块指针对齐 + 漂移 CI 门禁 | candidate |
| bet-y1q1-t1-03 | goals/current.yaml 复活 | candidate |
| bet-y1q1-t1-04 | 未入库产物普查 + D0 铁律门禁 | candidate |
| bet-y1q1-t1-05 | 仓库拓扑改造 — 单实例多租户 → 多实例单写者 | candidate |
| bet-y1q1-t1-06 | 子模块隔离 — PASW 覆盖 3→18, 拓扑改造后整体退役 | candidate |
| bet-y1q1-t1-07 | git 入口收口 — shim 强制走 swarm-git | candidate |
| bet-y1q1-t2-01 | signal-sources 注册表与感知面契约 | candidate |
| bet-y1q1-t2-02 | iris apple_mail 真实轮询打通 | candidate |
| bet-y1q1-t3-01 | MOS agent_belief 三表 schema 与写入路径 | candidate |
| bet-y1q1-t3-02 | SceneWatcher 决策日志真写 MOS | candidate |
| bet-y1q1-t4-01 | AdjudicationRecorded 事件与裁决存储 | candidate |
| bet-y1q1-t7-01 | scene-card 五档生命周期 schema | candidate |
| bet-y1q1-t7-02 | v10 失落产物重建并入库 | candidate |
| bet-y1q1-t7-03 | 公文场景砍到 3 node 并进 shadow | candidate |
| bet-y1q1-t8-01 | /inbox 决策收件箱最小版 | candidate |
| bet-y1q2-t1-01 | omo-debt + c2g 并入 omo | candidate |
| bet-y1q2-t1-02 | model-driven 去留判定 | candidate |
| bet-y1q2-t5-01 | durable timer — waiting_approval 跨进程存活 ≥7 天 | candidate |
| bet-y1q2-t5-02 | 回退边执行语义 + 次数上限 + 升级路径 | candidate |
| bet-y1q2-t6-01 | GaC 规则减法 — 清理会拦人却无违规历史的 required 规则 | candidate |
| bet-y1q2-t6-02 | ADR 分层 — 只分层不裁剪 | candidate |
| bet-y1q2-t6-03 | bin 脚本清理 — 归档零调用脚本, 不设数量目标 | candidate |
| bet-y1q2-t6-04 | 合成协作场景归档 221 → ≤40 | candidate |
| bet-y1q2-t6-05 | 减法配额制门禁上线 | candidate |
| bet-y1q2-t6-07 | B.D.S.K. 影子沙箱预演场 — 0-Touch 代码提交前对抗仿真 | candidate |
| bet-y1q2-t6-08 | 100% 责任归因代理链 — Subagent 全流程继承树审计 | candidate |
| bet-y1q2-t6-09 | AetherForge 动态算力与模型自动配比 | candidate |
| bet-y1q2-t6-10 | god-module 大文件 SRP 拆分 (3 个 >1500L 债 | candidate |
| bet-y1q2-t7-01 | 工程交付 dogfood 开 shadow | candidate |
| bet-y1q2-t8-01 | /outcomes 结果与校准面板 | candidate |
| bet-y1q3-t2-01 | 感知面第二根管子 (文件夹 / 日历 | candidate |
| bet-y1q3-t3-01 | MOS 双栈一致性观察 8 周 | candidate |
| bet-y1q3-t3-02 | Neo4j 生产启用 | candidate |
| bet-y1q3-t3-03 | 退役 mem0 / memtheta 仿真适配器 | candidate |
| bet-y1q3-t6-01 | gbrain + kairon 归并为 knowledge (不可逆点 | candidate |
| bet-y1q3-t7-01 | 知识场景召回被引用率上线 | candidate |
| bet-y1q4-t1-01 | Y1 表面积盘点与年度门 | candidate |
| bet-y1q4-t3-01 | 自主性阶梯 L0-L3 判据实现 | candidate |
| bet-y1q4-t4-01 | 真实评测集 v1 (≥200 条 | candidate |
| bet-y1q4-t5-01 | 并行会签 fork/join | candidate |
| bet-y1q4-t6-01 | aetherforge 并入 runtime | candidate |
| bet-y1q4-t7-01 | 公文场景 format_check 升 L2 | candidate |
| bet-y2q1-t3-01 | 世界模型 world_snapshot 全量 + delta | candidate |
| bet-y2q1-t3-02 | 意图模型接 goals / tasks 实时 | candidate |
| bet-y2q1-t3-03 | Agent 据心智模型决策 (脱离纯阈值 | candidate |
| bet-y2q2-t7-01 | 知识入库场景升 assisted | candidate |
| bet-y2q2-t7-02 | 中试平台 / 政策申报场景 draft → shadow | candidate |
| bet-y2q2-t8-01 | /inbox 每日习惯化改造 | candidate |
| bet-y2q3-t3-01 | 跨场景校准迁移 | candidate |
| bet-y2q3-t3-02 | 漂移监控与自动降级 | candidate |
| bet-y2q3-t6-01 | 减法第二轮维持 | candidate |
| bet-y2q4-t1-01 | Y2 年度门 + 愿景证伪检查 | candidate |
| bet-y2q4-t2-01 | 感知面第三 / 四根管子 | candidate |
| bet-y2q4-t3-01 | 多模型路由按实测成本优化 (v10 Stage γ 解冻 | candidate |
| bet-y3h1-t3-01 | 新场景冷启动 < 2 周 | candidate |
| bet-y3h1-t5-01 | 编排模板化 | candidate |
| bet-y3h1-t6-01 | 表面积不反弹审计 | candidate |
| bet-y3h1-t7-01 | 中试 / 政策申报升 assisted | candidate |
| bet-y3h2-t1-01 | 对外扩展决策 ADR (默认不做 | candidate |
| bet-y3h2-t1-02 | 三年终局门 | candidate |
| bet-y3h2-t4-01 | 复利收益归因报告 | candidate |
| bet-y3h2-t7-01 | 公文场景 routine (限格式类 | candidate |
| cockpit-debt-debt-1 | 治理技术债务：债务 | candidate |
| kos-q-growth-rolling | KOS 季度扩量持续监测 (rolling goal 关联 task | candidate |
| needs-human-batch2-physical-recovery-checklist | 机器恢复日验收清单（探测→G-DEL.3→G-DEL.1→S1 物理 KPI 解锁） | candidate |
| needs-human-p80-physical-hosts | P80 T2: expand physical hosts ≥4 + G-DEL.3 (stat | candidate |

> **补充规划**: `.omo/tasks/planned/vision-roadmap/` 子目录保留长期愿景路线图（4 YAML + 5 MD），不纳入标准 planned 任务计数。

## Completed Tasks (229 个)

> `tasks/done/` — 229 个顶层 YAML 文件，子目录按 Phase/主题分组存放历史任务。

近期关键完成里程碑（done/ 顶层）:
- P42-W0-W1-COMBO / P42-W2-COMBO — P42 治理面 SSOT 同步
- P43-W0-W3-COMBO — P43 4 wave 全面实施
- P44-W0-W4-COMBO / P44-REMEDIATE-WF-CONV-CLOSE / P44-SUBMODULE-PIN — P44 HTTP-MCP 收敛与收尾
- P45-DOC-LIFECYCLE / P45-W0-W3-COMBO — P45 BOS URI 收敛
- P46-MOF-IMPL — P46 MOF 实现
- P47-P52 系列 — CI 覆盖、GBR TODO、drafts 清理、MDrift 关闭等
- REMEDIATE-ARC-CONV-P1-CRON — 架构收敛 P1 完成
- SHAREDBRAIN-FORMAL-DECISION — SharedBrain 归档决策
- TASK-DEBT-CLOSURE-EVIDENCE-20260620 — 债务关闭 evidence
- TASK-KAIRON-MYPY-STRICT — kairon mypy strict 启用
- TASK-9B363829 — BOS 声明/执行鸿沟修复 (evidence-smoke resolve_rate=100)
- TASK-26348641 — 自反馈闭环 (feedback-loop-guard 3 维度 + mypy MYPYPATH=src baseline-gate)

完整列表请见 `tasks/done/` 目录及子目录。

## Archived Tasks (6 个顶层)

> `tasks/archived/` — 6 个顶层 YAML 文件，含历史 imported 任务与 legacy-normalized 子目录。

顶层 archived 任务:
- P35-ROADMAP
- OPC-P6-SELF-EVOLUTION-nop-20260614T114209Z
- OPC-P15-KAI-02
- P2-HARDCODED-PATHS-TICKET
- TASK-C2G-V2-EVOLUTION
- IMPORTED-58d3f8

> **注**: 子目录 `legacy-normalized/` 中包含 REMEDIATE-ARC-CONV-P2-CACHE 至 P6-CALIBRATE 等历史收敛任务，已在 BET-ARCH-CONVERGENCE 完成上下文下归档。

## Blocked Tasks

当前无阻塞任务。

---
*Updated: 2026-08-08 (依据 `omo state sync-tasks` 与真实目录重算: done=229, planned=68, active=0, archived=6 顶层)*
*Sync command: `omo state sync-tasks`*
