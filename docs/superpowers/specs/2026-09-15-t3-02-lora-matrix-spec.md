---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-15
last-reviewed: 2026-09-15
bet_id: BET-Y2Q2-T3-02
risk_level: L1
human_gate: true
value_indicator_policy: false
type: ssot
---

# T3-02 个人文风四域 LoRA 适配器矩阵与语气自适应调节设计

## 0. 背景与依赖

- 依赖 `BET-Y1Q3-T10-118`（status: done，delivery_accepted）：已交付三域
  （gov/tech/email）蒸馏与 `LoraAdapterManager` 热插拔（注册表持久化 +
  `activate/deactivate` + `adapter_for_domain` + `distill_all` 诚实派发）。
- 本 BET 从三域扩展为**四域矩阵**：政务公文（gov）/ 技术架构（tech）/
  对外协作（collab）/ 随想随笔（essay），推理时按任务领域动态切换，
  叠加 ROUGE-L 语气门 + 中英防遗忘守卫 + 严重失真熔断回退中立模板。

## 1. In scope（最小闭环）

1. `projects/omlxc/src/omlxc/dataplane/lora/`（子仓新包）：
   - `matrix.py`：`DOMAINS`（4 域）、`ADAPTER_NAMES`
    （lora-gov-v2 / lora-tech-v2 / lora-collab-v1 / lora-essay-v1）、
     `route_domain(task_text)`（关键词路由，特异性排序
     collab → essay → tech → gov，gov 为默认兜底）、`LoraMatrix`
     （独立注册表 `.omo/state/lora-matrix.json`，不碰 T10-118 注册表；
     `activate/deactivate/adapter_for_domain/list_matrix`；
     `switch(domain)` 无缝切换只写注册表、返回
     `{prev, current, reloaded: False}`）、`distill_status(domain,
     buffer_path)`（诚实三态：ok / pending_samples /
     needs_mlx，绝不伪造权重）、`regulate(candidate, reference,
     threshold=0.75)`（ROUGE-L 门 + 失真熔断建议）。
   - `eval_tone.py`：纯标准库 ROUGE-L（中文按字粒度 LCS）、
     `revision_rate(before, after)`（= 1 − ROUGE-L）、
     `guard_protected_terms(text)`（中英专名防遗忘正则守卫）。
   - `test_matrix.py`：自包含断言Runner，供
     `uv run python -m omlxc.dataplane.lora.test_matrix` 调用，
     exit 0 即全过（路由四域/特异性排序/切换往返/未知域/
     诚实三态/ROUGE-L 已知值/修订率/守卫命中）。
2. `projects/spine/src/spine/cognitive/lora_tone.py`（主仓新文件）：
   - `ToneAdapter`：`directives_for(task_text, candidate=None,
     reference=None)` 复用四域路由表 + `MindModelRouter` 的 persona
     tone；ROUGE-L < 0.75 时 `fallback_neutral=True` 并熔断标记；
     永不抛异常（circuit breaker 全包裹，失败即中立）。
   - `projects/spine/src/spine/cognitive/test_lora_tone.py`：
     自包含Runner（`uv run python -m spine.cognitive.test_lora_tone`）。
3. 本 spec + ledger `accepted_specifications` 恰 1 条绑定 +
   `.omo/_knowledge/retros/BET-Y2Q2-T3-02.md`。

## 2. Out of scope（non-goals）

- 不在非必要场合强行套用模板（ledger non_goals 原样继承）。
- 不做真实权重训练（本机无 MLX 后端时 `distill_status` 诚实报
  `needs_mlx`； collab/essay 域样本不足时报 `pending_samples`）。
- 不改 T10-118 注册表文件与 cockpit 命令（只新增面，不回退旧面）。

## 3. 正确性要点

- 特异性排序是正确性前提（T10-118 retro 实证：gov 宽词"函"会吃掉
  窄域词）：collab 的"合作/签约/洽谈"、essay 的"随笔/随想/手记"、
  tech 的"架构/ADR/接口"一律先于 gov 宽词匹配。
- `switch()` 无缝 = 零 reload：只换注册表指针，推理侧下次
  `adapter_for_domain` 即见新值；返回体显式 `reloaded: False` 防误解。
- 语气门阈值 0.75 与 done_when 的 ROUGE-L ≥ 0.75 同源；
  熔断条件（严重失真）→ 中立模板，与 ledger circuit_breaker 对齐。

## 4. 验证

- `uv run python -m omlxc.dataplane.lora.test_matrix` → exit 0
  （子仓 `projects/omlxc` 内执行）。
- `uv run python -m spine.cognitive.test_lora_tone` → exit 0。
- `make gac-local-gate` → exit 0。

## 5. 交付形态

- 子仓分支 `agent/t3-02-lora-matrix`：commit + push；主仓以 pointer
  bump 引用（子模块三步走），主仓 PR 只含：spec、spine 新增、
  ledger 绑定+状态、retro、pointer。
