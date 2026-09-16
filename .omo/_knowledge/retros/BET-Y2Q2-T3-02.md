---
schema: bet-retro/v1
bet_id: BET-Y2Q2-T3-02
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-15
type: ephemeral
---

# BET-Y2Q2-T3-02 retro — 四域 LoRA 矩阵与语气自适应调节

## What changed（工程交付）

- **子仓 `omlxc` 新包 `dataplane/lora/`**（分支 `agent/t3-02-lora-matrix`）：
  `eval_tone.py`（纯标准库字符粒度 ROUGE-L + `revision_rate` +
  中英专名防遗忘守卫）、`matrix.py`（四域路由，特异性排序
  collab → essay → tech → gov；独立注册表 `lora-matrix.json` 不碰
  T10-118 注册表；`switch()` 纯指针交换 `reloaded: False`；
  `distill_status()` 诚实三态；`regulate()` 0.75 语气门 + 失真熔断）、
  `test_matrix.py`（36 断言自包含 Runner）。
- **主仓 `spine/cognitive/lora_tone.py`**（新）：`ToneAdapter`
 （四域路由镜像 + `MindModelRouter` persona tone；ROUGE-L < 0.75
  回退中立；全包裹永不抛异常）+ `test_lora_tone.py`（13 断言）。
- **spec** `docs/superpowers/specs/2026-09-15-t3-02-lora-matrix-spec.md`
  + ledger `accepted_specifications` 恰 1 条绑定（digest 与文件一致）。

## Q3 (打假)

- done_when[0] 的权重包：本机无 MLX 后端、collab/essay 域真实样本不足，
  `distill_status` 只能诚实报 `needs_mlx` / `pending_samples`——
  不以合成权重冒充（T10-118 同款诚实契约）。
- done_when[2] 的 ROUGE-L ≥ 0.75 / 修订率 −30%：门控框架与度量已就位，
  真实 adapter 训出后跑 `regulate()` 度量；当前以固定文本对证明门逻辑。
- 特异性排序复用 T10-118 教训（gov 宽词兜底最末），用例锁定：
  "对外协作会议通知"→collab、"通知：随笔漫谈"→essay、
  "架构评审后部署审批"→tech。

## Q4 (遗留 → 收账门)

- 四域真实权重：待 MLX 后端（或 M4 节点路由）+ collab/essay 域样本
  ≥8 条/域后跑 `distill_all` 系蒸馏；届时 `activate()` 挂载。
- 对齐度 ≥30% 的评估需 adapter 真训后跑 `regulate()` 前后对比。
- 偏序备注：`start` 曾因 `WORK_PACKET_COMPILER_UNAVAILABLE`
  （ecos 子模块克隆中）阻塞，实现先行、run 登记随后补齐；
  claim 需 affected-graph 先行（含 `workspace-root` 才认领 retro 面）。

## Verification

- `uv run python -m omlxc.dataplane.lora.test_matrix` → 36/36（子仓 venv）
- `uv run python -m spine.cognitive.test_lora_tone` → 13/13
- 既有回归：`test_lora_manager.py` + `test_mind_quartet` 全过
- `make gac-local-gate` → exit 0
