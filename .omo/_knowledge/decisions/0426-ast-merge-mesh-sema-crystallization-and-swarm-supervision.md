---
id: ADR-0426
status: archived
lifecycle: spec
owner: agora
last-reviewed: '2026-08-25'
type: ssot
---

# ADR-0426: AST 语义级合流防腐、SEMA 自动结晶与蜂群常驻看护架构

- **状态**: Accepted
- **日期**: 2026-08-25
- **决策者**: @Builder, @Sage, @Devil, @Keeper (B.D.S.K. 虚拟董事会)
- **关联**: ADR-0425 (Agent LSP & In-Memory Bus), ADR-0203 (Requirement Iteration Workflow)

---

## 1. 背景与问题陈述 (Context & Problem)

在多 Agent 高频并发协同场景下，系统面临三大核心瓶颈：
1. **Git 文本合流摩擦**：YAML/JSON/Markdown 结构化文件因列表项先后顺序不同，Git 行级比较频繁误报 Merge Conflict；
2. **踩坑经验沉淀脱节**：Agent 在运行态遇到的高频失败模式（如锁竞争、端口冲突）无法自动反哺为全仓共享的 SOP 规范；
3. **内存总线常驻韧性**：Agora 2.0 (:7432) 总线需要原生系统级守护托管与并发自愈保障。

---

## 2. 核心架构决策 (Decisions)

### D1: AST 语义级三路合并驱动 (`bin/gac/ast-merge-mesh.py`)
* 注册 Git 自定义 Merge Driver `merge.ast-mesh`，在 `.gitattributes` 中为 `*.yaml`, `*.json`, `*.jsonl`, `*.md` 全量绑定；
* 列表项基于主键（`id`, `name`, `key`）进行语义节点对齐合并，彻底消除行级假冲突；真冲突时插入标准 Conflict Markers 并向总线报警。

### D2: SEMA 记忆自蒸馏与技能自动结晶 (`bin/ssot/sema-distill.py`)
* 接入每日 10:30 知识熔炉定时流水线（`knowledge-foundry-cron.py`）；
* 自动挖掘运行轨迹与错误日志，聚类高频失败模式并自动生成标准化 `.agents/skills/auto-crystallized/<skill>/SKILL.md` 技能包。

### D3: Agora 2.0 守护服务托管与 50-Agent 混沌压测
* 在 `cockpit daemon` 增加 `install-service` / `uninstall-service` / `status` / `restart` 命令，生成 macOS `launchd` plist / Linux `systemd` 服务；
* 配套 `bin/_archive/2026-08-conv3/daemon-stress-test.py` 压测套件，实测 50-Agent 并发 QPS > 90 且 P99 延迟 < 1.0ms。

### D4: 全景座舱多维观测集成 (`cockpit tui` / `omo-status`)
* 在 `SwarmGlobalState` 与 `SwarmStateCollector` 中打通 Agora 2.0 守护总线实时探测；
* 顶层看板提供 `BUS :7432 ●` 呼吸灯指示与全仓 14 仓指针健康度实时联动。

---

## 3. 验收与实证 (Verification & Evidence)

1. `python3 bin/gac/ast-merge-mesh.py`: YAML/JSON 列表三路合并 0 冲突；
2. `python3 bin/_archive/2026-08-conv3/daemon-stress-test.py --chaos`: 50-Agent 压测 PASS (P99 = 0.26ms)；
3. `python3 bin/ssot/sema-distill.py`: 扫描并验证自蒸馏技能生成逻辑；
4. `cockpit daemon status`: 🟢 Agora 2.0 守护总线运行中 (:7432)。
