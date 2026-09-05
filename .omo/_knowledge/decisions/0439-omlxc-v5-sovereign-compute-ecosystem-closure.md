---
id: ADR-0439
status: accepted
lifecycle: spec
owner: xiamingxing
last-reviewed: 2026-08-30
type: ssot
---

# ADR-0439: 次世代 omlxc V5.0 主权算力织网全生态闭环与长期治理运维体系 (DMA Daemon、署名Diff自进化闭环、Cockpit Spine CLI、Experience Replay 防灾难遗忘)

- **状态**: ACCEPTED
- **日期**: 2026-08-30
- **作者**: starlink-awaken / xiamingxing
- **关联**: ADR-0436, ADR-0435, ADR-0434, ADR-0197, ADR-0203

---

## 1. 背景与核心动机 (Context & Motivation)

在 ADR-0436 确立了次世代 omlxc V5.0 的五大核心前沿（雷雳5 120Gbps P2P 零拷贝 DMA、在线 LoRA 热插拔、共生草稿头蒸馏、视觉 Patch 直通、Cockpit HUD）之后，为了实现“织星是夏明星一个人的业务操作系统，唯一职责是把外部信号变成他愿意署名发出去的东西，并记住每次改了什么”的系统终极愿景，必须完成算力层与业务真值流、全生命周期运维与治理门禁的终态工程闭环。

---

## 2. 架构决策与闭环实现 (Architecture Decision & Realization)

### 1. 多机守护进程与自愈探活体系 (`omlxc.daemon.dma_daemon`)
- **秒级探活与弹性降级**：每 1 秒探活物理雷雳链路（120Gbps / 0.21ms 换页延迟），断开时透明回退至 10GbE / TCP 备用管道；
- **自愈重连机制**：采用指数退避重连（1s → 2s → 4s → 最大 30s）；
- **75% 阶梯显存门禁跨机溢出**：当 MBP M5 Max 统一内存使用率达到 75%（96GB）阈值时，自动触发 Paged KV 块向 Mac mini M4 溢出迁移；
- **遥测状态持久化**：每个探测周期向 `.omo/state/mesh-telemetry.json` 写入全量快照；
- **macOS launchd 原生支持**：提供 `launchd/com.omostation.omlxc-dma-daemon.plist` 与 `--generate-plist` 命令行生成支持。

### 2. 夏明星专属署名 Diff 闭环与 Experience Replay 防灾难性遗忘 (`experience_replay.py`)
- **署名 Diff 捕获**：在 Cockpit / `value-evolution-connector.py` 中记录夏明星审议采纳的修改内容；
- **Experience Replay 缓冲区**：采用水塘抽样（Reservoir Sampling，容量 2048 样本），在闲时微调时按 30% 历史回放 / 70% 新鲜样本混合构建训练 Batch，彻底阻断灾难性遗忘（Catastrophic Forgetting）；
- **闲时在线蒸馏**：通过 BOS `bos://compute/omlxc/lora` 调度至 Mac mini M4 空闲算力异步训练，生成专属适配层。

### 3. Cockpit Spine CLI 统一接入层 (`cockpit.commands.spine`)
- **`cockpit spine draft --prompt <>`**：经 `bos://compute/aetherforge/infer` / `omlxc fabric triage` 路由本地主权模型生成草稿；
- **`cockpit spine sign --original <> --signed <>`**：提交署名修改，原子写入 `.omo/state/lora-replay-buffer.jsonl` 并关联北极星价值增长；
- **`cockpit spine diff / replay`**：直观表格查看各领域署名样本蓄水池；
- **`cockpit spine status`**：展示实时 DMA 链路模式、带宽、延迟、显存占用与活跃 LoRA 适配器；
- **`cockpit spine distill`**：一键派发闲时蒸馏微调任务。

---

## 3. 生态衔接与全景验证 (Verification & Impact)

| 验证维度 | 验证手段 | 达标结果 |
|---------|---------|---------|
| 守护进程与溢出 | `pytest projects/omlxc/tests/unit/test_dma_daemon.py` | 4/4 全部通过，秒级状态落盘与溢出迁移逻辑完备 |
| 经验回放防遗忘 | `pytest projects/omlxc/tests/unit/test_experience_replay.py` | 2/2 全部通过，水塘抽样与混合 Batch 比例精确 |
| Cockpit Spine CLI | `pytest .subtrees/cockpit/tests/test_spine_cli.py` | 2/2 全部通过，sign / diff / status / distill 闭环全通 |
| 价值进化接线 | `python3 bin/gac/value-evolution-connector.py --record-diff` | 成功落盘并关联北极星价值度量 |

---

## 4. 后续演进 (Future Roadmap)

1. 将 `omlxc-dma-daemon` launchd 守护进程整合进 `make resident-daemon` 常驻进程群；
2. 持续沉淀夏明星专属署名 Diff 样本库，每达到 128 条自动触发增量 LoRA 权重编译。
