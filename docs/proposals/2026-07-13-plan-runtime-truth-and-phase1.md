# 规划提案 · 让绿色变真 + 迈出多机第一步

> 状态: **草案 (proposal, 未入 SSOT)** · 生成日期: 2026-07-13
> 正式落地前应经 `c2g-spec-ingress` 入库为 bet，勿直接改 `.omo/`。
> 战略判断依据: BRIEF.md / VISION-ROADMAP.md / health.yaml (2026-07-09) / weekly-daemon-summary (2026-07-12) / bos-declaration-execution-gap-2026-06-24.md

---

## 0. 一句话背景

治理脚手架已过度成熟（W1–W4 全 done、Phase 42、113+ ADR），产品愿景（蜂群/多机/个人大脑）几乎零启动，而 84 的健康分是"治理绿、运行时黄"——runtime 只贡献 18/30，daemon 在线率 60%，BOS 存在声明/执行鸿沟。本规划按 **A→B 顺序执行，C 作为纪律约束**。

---

## 1. 三条 Track 与总体节奏

| Track | 目标 | 周期 | 启动条件 |
|-------|------|------|----------|
| **A · Runtime Truth** | 把健康分的运行时项做实，消除声明/执行断层 | ~2 周 | 立即 |
| **B · Roadmap Phase 1 切片** | 2 机状态同步从 PPT 变成可验收里程碑 | ~3–4 周 | A5 通过后 |
| **C · 过度工程纪律** | 停止元机器生长 + 一次减负审计 | 贯穿 + 并行 | 立即 |

**红线 C0（贯穿 A/B 全程）**：除非直接服务于某个验收标准，**不新增任何 registry / 契约 / ADR 流程 / phase**。唯一例外是 B2（状态同步 ADR，因其直接服务 B 的验收）。

---

## 2. Track A — Runtime Truth（先决条件）

> 核心逻辑：你现在无法信任自己的健康分，任何上层决策都建立在可能失真的信号上。这是前置条件，不是可选项。

### A1 · 重新审计 BOS 声明/执行鸿沟
- **目标**：产出当前真实的"声明 alive vs 实际 resolve 成功"数字，替换 6/24 的 102:0 旧快照（该快照已部分修复：`mcp_server.py` 现已广泛存在）。
- **范围**：全量跑 `resolve_bos_uri()`；失败 URI 按根因分类（缺 mcp_server.py / 路径-模块不匹配 / 包未安装）。
- **验收**：可复现的 resolve 通过率报告 + 失败清单 CSV。
- **profile**：`governance-audit` ｜ **依赖**：无 ｜ **估时**：0.5 天

### A2 · 修复剩余 stdio 包 resolve 失败
- **范围**：按 A1 清单逐包修复——补齐缺失 `mcp_server.py`、对齐 `pyproject packages` 与 resolver 生成的 `-m` 模块路径（forge 类问题）。
- **验收**：resolve 通过率 ≥95%，新增回归测试锁定。
- **profile**：`project-code-change` ｜ **依赖**：A1 ｜ **估时**：2–3 天

### A3 · daemon 在线率 60%→95%
- **范围**：修复 audit-rollout 管道 `returncode:1 / fallback / failed_count:1`（见 `runtime/omo/_delivery/audit-rollout/2026-07-12-weekly-daemon-summary.json`）；体检所有 launchd 常驻服务，定位掉线的 40%。
- **验收**：`service_online_ratio ≥0.95` 且连续 3 次 weekly summary 无 failed。
- **profile**：`project-code-change` ｜ **依赖**：无（可与 A2 并行）｜ **估时**：2–3 天

### A4 · 把 runtime 真实度纳入健康分门禁
- **范围**：将 BOS resolve 通过率 + daemon online_ratio 作为硬指标纳入 health composite 的 runtime 项，堵住"声明绿、运行时黄"的稀释漏洞。走 `omo` CLI/broker，**禁止直接写 `.omo/`**。
- **验收**：health.yaml runtime 贡献反映真实值（不再恒定 18/30）。
- **profile**：`governance-state-mutation` ｜ **依赖**：A2 + A3 ｜ **估时**：1 天

### A5 · Track A 结项验证
- **范围**：复跑健康分与 resolve 全量，确认 runtime 贡献接近 30/30、online_ratio≥0.95、resolve≥95%。
- **验收**：结项复盘文档（作为 B 立项的地基证明）。
- **profile**：`governance-audit` ｜ **依赖**：A4 ｜ **估时**：0.5 天

---

## 3. Track B — Roadmap Phase 1 最小切片（2 机状态同步）

> 只做 Roadmap M1 一个可验收里程碑：**2 机状态同步延迟 <100ms**。不碰多角色/蜂群/负载均衡。用它倒逼验证治理+runtime 基建能否撑住分布式。

### B1 · 立项 Phase 1 bet
- **范围**：通过 `c2g-spec-ingress` 正式入库 bet，唯一验收锁定"2 机状态同步延迟 <100ms"。Appetite 建议 2 周。**明确禁止范围蔓延**。
- **验收**：bet 入库，scope 单一。
- **profile**：`c2g-spec-ingress` ｜ **依赖**：A5 ｜ **估时**：0.5 天

### B2 · 分布式状态同步设计 ADR
- **范围**：CRDT vs 最终一致性选型、增量同步+压缩、冲突解决、故障场景。runtime+omo。（B 里唯一允许的新流程产物。）
- **验收**：ADR 评审通过并进 INDEX。
- **profile**：`mof-model-change` 或 `governance-state-mutation` ｜ **依赖**：B1 ｜ **估时**：1–2 天

### B3 · 跨机通信协议最小实现
- **范围**：ecos+runtime 实现最小可用跨机通道（仅够支撑 2 机 state sync，不做通用消息总线）。
- **验收**：两进程/机器间可建通道并传状态增量。
- **profile**：`project-code-change` ｜ **依赖**：B2 ｜ **估时**：3–5 天

### B4 · 2 机同步 PoC + 延迟基准
- **范围**：runtime+omo 实现状态同步 PoC + 延迟基准测试台。
- **验收**：可重复测出端到端同步延迟。
- **profile**：`project-code-change` ｜ **依赖**：B3 ｜ **估时**：3–5 天

### B5 · Phase 1 验收
- **范围**：2 机环境正式验收，延迟 <100ms，闭环 bet + 复盘。
- **验收**：延迟达标，M1 里程碑签收。
- **profile**：`governance-audit` ｜ **依赖**：B4 ｜ **估时**：1 天

---

## 4. Track C — 过度工程纪律

### C0 · 红线（非任务，是约束）
A/B 全程冻结新增治理机器。每次有人想加 registry/gate/ADR，先问：这直接服务哪个验收标准？答不上就不加。

### C1 · 治理过度工程量化审计
- **范围**：给每个 registry / GaC gate / ADR 流程算 ROI（触发频率、拦截真实问题数、维护成本），标出最低 ROI 的可冻结/合并项。
- **验收**：一份"减负候选清单"（仅审计，不落地改动，避免抢 A/B 资源）。
- **profile**：`governance-audit` ｜ **依赖**：无（并行）｜ **估时**：1–2 天

---

## 5. 依赖关系图

```
A1 ─► A2 ─┐
          ├─► A4 ─► A5 ─► B1 ─► B2 ─► B3 ─► B4 ─► B5
A3 ───────┘
C1  (独立并行)
```

关键路径：A1→A2→A4→A5→B1→B2→B3→B4→B5。A3 与 A2 并行，C1 全程可并行。

---

## 6. 如何分配给其他 agent

每个任务用其 profile 走标准 workflow 生命周期（见 CLAUDE.md §5）：

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> \
    --profile <上表 profile> --objective "<任务标题>"
# → claim <run-id> --path <涉及路径>
# → verify <run-id> --from-diff --execute
# → closeout <run-id>
```

建议一次只放行**关键路径上的下一个未阻塞任务** + C1 并行，避免多 agent 抢同一子模块导致 submodule dirty（P60 坑）。

---

## 7. 成功判据（3–6 周后回看）

1. 健康分从"治理主导的 84"变成"运行时真实的 X"——即便分数下降，也是**可信的**分数。
2. BOS resolve ≥95%、daemon online ≥95%。
3. 多机从 0 到 1：2 机状态同步 <100ms 可复现。
4. C1 清单落地至少 1 项治理减负，元机器停止净增长一个周期。

**最该警惕**：不要因为治理浪好推、闭环漂亮，就回到 Phase 43/44 继续刷治理债——那是舒适区，边际价值已见底。
