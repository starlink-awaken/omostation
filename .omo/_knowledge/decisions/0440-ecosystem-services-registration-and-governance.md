---
id: ADR-0440
status: accepted
lifecycle: spec
owner: xiamingxing
last_updated: 2026-08-30
---

# ADR-0440: 全生态服务 SSOT 登记、BOS URI 全生命周期路由注册与 Agora FastMCP 主权算力工具链挂载

- **状态**: ACCEPTED
- **日期**: 2026-08-30
- **作者**: starlink-awaken / xiamingxing
- **关联**: ADR-0439, ADR-0437, ADR-0436, ADR-0203, ADR-0199

---

## 1. 背景与动机 (Context & Motivation)

在 ADR-0439 完成了次世代 omlxc V5.0 主权算力织网、DMA 守护进程与夏明星专属署名 Diff 经验回放闭环的基础工程落地后，根据全仓单一真相源（SSOT）治理与多智能体统一协议规范，所有新增的算力总线与主干真值流能力必须全面接入：
1. **BOS URI 声明表**（`projects/agora/etc/bos-services.yaml`）；
2. **Agora FastMCP 工具发现与路由链**（`agora.server.tools_bos`）；
3. **全局系统守护服务表**（`.omo/_truth/registry/services.yaml`）；
4. **统一 CLI 命令树**（`omlxc fabric dma / replay`）。

确保本地与跨机 AI Agent（如 Claude Code, AetherForge, Cursor 等）能够以纯净契约自发现、自调度和自迭代。

---

## 2. 核心架构决策与实现 (Architecture Decisions & Implementation)

### 1. BOS URI 服务声明规范 (`projects/agora/etc/bos-services.yaml`)
- **`bos://compute/omlxc/replay`**：omlxc 经验回放池状态、水塘抽样与防遗忘混合 batch 统计；
- **`bos://spine/draft`**：Cockpit/Spine 本地主权草稿生成与 AetherForge/omlxc 推理代理；
- **`bos://spine/sign`**：Cockpit/Spine 夏明星署名 Diff 经纪人录入与经验回放自适应进化；
- **`bos://spine/diff`**：Cockpit/Spine 署名 Diff 对比分析与经验样本池浏览；
- **`bos://spine/status`**：Cockpit/Spine 物理算力织网与主干真值流状态监控；
- **`bos://spine/distill`**：Cockpit/Spine 触发 Mac mini M4 闲时在线 LoRA 蒸馏。

### 2. Agora FastMCP 工具链集成 (`agora.server.tools_bos.spine`)
- 新增 `agora.server.tools_bos.spine` 模块，提供跨进程与跨子仓桥接：
  - `bos_spine_draft`
  - `bos_spine_sign`
  - `bos_spine_diff`
  - `bos_spine_status`
  - `bos_spine_distill`
  - `bos_mesh_dma_status`
- 在 `registration.py` 中挂载 `@mcp.tool()` 装饰器，并注入 `list_bos_tools()` 统一索引字典，支持 Agent 零配置自发现。

### 3. 全局常驻守护服务登记 (`.omo/_truth/registry/services.yaml`)
- 注册 `omlxc.dma_daemon`（`label: com.omostation.omlxc-dma-daemon`）：
  - 调度器：macOS launchd；
  - 触发策略：`keepalive: crashed`，`run_at_load: true`；
  - 活性检查：基于 `.omo/state/mesh-telemetry.json` 文件的保鲜时间戳（max_stale_hours: 24）；
  - 入口：`projects/omlxc/src/omlxc/daemon/dma_daemon.py`。

### 4. omlxc CLI 原生命令扩展 (`omlxc.cli fabric dma / replay`)
- 在 `fabric_app` 下扩展 `dma` 与 `replay` 命令，支持 Rich Panel 终端可视化与 `--json` 机器可读格式无缝输出。

---

## 3. 验证与门禁合规 (Verification & Impact)

| 检查项 | 验证命令 | 结果 |
|-------|---------|------|
| omlxc 单元与集成测试 | `cd projects/omlxc && uv run pytest` | **1119 passed, 1 deselected** (0 errors) |
| omlxc CLI 命令输出 | `uv run python -m omlxc.cli fabric dma/replay --json` | 成功输出 Rich Panel 与合法 JSON 负载 |
| Agora BOS 路由与去重 | `pytest tests/integration/test_bos_routing_chain.py` | **26 passed** (0 重复 URI) |
| Agora MCP 服务发现 | `pytest tests/test_discovery.py` | **4 passed** (支持 subtree .venv 路径探测) |
| 全局能力同步 | `python3 bin/capability-sync.py sync && check` | 0 drift, 0 orphan |
| 调度器编译一致性 | `python3 bin/scheduler-compile.py --check` | `ok: true, drift_count: 0` |

---

## 4. 总结与后续运营 (Summary & Operational Continuity)

通过本 ADR 的落地，omlxc V5.0 的物理雷雳链路、自愈守护、经验回放和主干真值流工具全部被正式纳入 Workspace 治理体系，成为受控、可审计、可进化的长效生产力基础设施。
