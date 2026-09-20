---
schema: bet-retro/v1
bet_id: C2-scene-adaptive
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-20
type: ephemeral
completed_at: 2026-09-20
---

# Retro: C2.2 — scene-card-autogen (场景自适应)

## Summary

新增 `bin/ssot/scene-card-autogen.py` — C2.2 场景自适应生成器.
3 个子命令:
1. `scaffold` — 给定 scene-id + domain + description, 生成完整 scene-card/v3 YAML 草稿
2. `from-signal` — 从 signal (e.g. `email.received:invoice`) 反推 scene_id + description
3. `list-templates` — 扫描 `.omo/_truth/scenarios/v3/` 列出已有 scene, 供 pattern mining

附带 schema 推断 (domain→scene_class, description→scene_type) 和
slug 标准化 (camelCase / dot.notation → kebab-case).

## What went well

- **schema 驱动**: 直接套用 scene-card/v3 现有 schema, 不重新定义结构
- **slug 实用**: XMLParser / calendar.event.upcoming / fooBarBaz 三类常见命名都
  正确转 kebab-case
- **可观测性**: list-templates 输出场景库总览, 后续可作 pattern mining 起点
- **零 LLM 依赖**: 纯规则 + 模板填充, 0 API cost, 跑得快 (<0.1s)
- **16 单元测试覆盖**: slug 4 类 + 推断 4 类 + scaffold/from-signal 4 类 + yaml 4 类

## What was learned

- **camelCase 多层大写需要先拆分**: XMLParser 拆 XML + Parser, 不只是 aB → a-B
  (否则那才是 XML 才停). 单独一次 replace 不够, 要先识别 A+B+ 小写 a 边界
- **signal 解析**: 多数信号形如 `ns.verb.target[:filter]`, split(':', 1) 防 filter
  含冒号
- **PyYAML 可选**: 离线场景没装 yaml 时, 自带的 `_yaml_inline()` 简化输出
  也能保证可读性
- **scene-card/v3 已 70 个 scene**: list-templates 输出真实分布, 多数 domain
  是 work, scene_type 多是 inbound, lifecycle 多 routine

## What to improve

- **scene_id 冲突检测**: scaffold 不检查是否已存在. 需加 `--force` 或自动
  加序号后缀
- **未连 journey**: scaffold 不自动生成 journey spec, 只生成 scene. 后续可
  串到 bin/ssot/scene-journey-autogen.py
- **未跑 mof-scene-validate**: 生成的 YAML 还没过 schema 校验器. 加 --validate
  flag 自动调用

## Metrics

- Files added: 2 (bin/ssot/scene-card-autogen.py 220L, tests/bin/test_scene_card_autogen.py 130L)
- Files modified: 0 (script-registry 自动建 yaml)
- Files archived: 1 (bin/ssot/prune-and-register.py)
- Tests: 16/16 pass in 0.20s
- Scene schema: scene-card/v3 (70 现有 scenes)
- Sub-commands: 3 (scaffold / from-signal / list-templates)
- PR: TBD
- Total LOC delta: +350

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| `bin/ssot/scene-card-autogen.py` 实现 | ✅ |
| 3 子命令 (scaffold / from-signal / list-templates) | ✅ |
| scene-card/v3 schema 默认模板 | ✅ |
| domain → scene_class 推断 (work/health/knowledge/research/governance) | ✅ |
| description → scene_type 推断 (inbound/outbound/cycle) | ✅ |
| slug 标准化 (camelCase / dot.notation → kebab-case) | ✅ |
| yaml 输出兼容 PyYAML 缺失场景 | ✅ |
| list-templates 列出 70 scenes 真实分布 | ✅ |
| 16 单元测试 | ✅ |
| script-registry 登记 | ✅ |
| ruff check 0 errors | ✅ |
| bin-quota 守恒 (归档 prune-and-register.py) | ✅ |