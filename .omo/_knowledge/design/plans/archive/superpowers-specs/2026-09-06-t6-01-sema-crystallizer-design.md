---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y2Q2-T6-01
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T6-01 SEMA 防踩坑信念自结晶与技能热重载设计

## 1. 目标

SEMA 引擎升级：从署名修改 Diff（T10-115 规则库）与 CI 拦截记录中自动
反向萃取防踩坑信念；**连续 2 次同类人工纠偏自动触发结晶管线**，生成
符合规范的 SKILL.md 与测试用例，注入 `.agents/skills/` 并秒级热加载
（<500ms，无需重启服务）。

## 2. In scope

1. `projects/omo/src/omo/resident/sema_crystallizer.py`（新文件）：
   - `CorrectionLedger`：纠偏事件账本（签名 diff 规则命中 / CI 拦截
     记录归一化为 correction 事件，key=pattern+type）。
   - `crystallize_if_ready(key)`：同类事件连续 ≥2 次即触发结晶——
     生成 `SkillCandidate`（SKILL.md 文本：frontmatter
     name/description 规范 + 触发条件 + 操作步骤 + 反例）+ 配套
     pytest 骨架。
   - `install(skill)`：写入 `.agents/skills/auto-crystallized/<name>/`
     并刷新 INDEX；`hot_reload()`：manifest mtime 哨兵 +
     `reload_skills()` API（<500ms，无服务重启）。
   - `watch()` 常驻探测：hard-negative-rules.jsonl 与 CI 拦截记录
     的新增事件。
2. `.agents/skills/auto-crystallized/SKILL.md`（新）：首个结晶产物
   （以真实规则库中的 terminology_replace 类规则为素材生成示例）。
3. `.agents/skills/INDEX.md`（增量）：索引刷新（含 auto-crystallized）。
4. `projects/omo/tests/unit/resident/test_sema_crystallizer.py`（新）：
   触发阈值、SKILL.md 规范、热加载延迟断言、INDEX 刷新。

## 3. Out of scope

- 不训练模型；规则萃取本体属 T10-115（本 bet 消费其规则库）。
- 不改 agent-workflow.py 的 suggest 机制（INDEX 为静态索引）。
- 真实 CI 拦截流接入以适配器接口交付，gerrit/GitHub 记录源为部署配置。

## 4. 验收（对齐 ledger done_when）

1. 同类纠偏事件第 2 次到达即触发结晶（第 1 次不触发——阈值断言）。
2. 产物 SKILL.md 含规范 frontmatter 与反例，测试用例可运行。
3. `hot_reload()` 延迟 <500ms（perf_counter 断言）且 INDEX 含新条目。
4. 单测全部通过。
