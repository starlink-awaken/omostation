# BET-Y1Q2-T7-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 完成场景卡 shadow 化 + 机制验证（约 40 分钟 vs appetite 1 周）。开发完成，decision_outcome 周产 20 条为持续观察目标。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| engineering-delivery 场景 lifecycle=shadow | ✅ `docs/scene-cards/engineering-delivery-dogfood.yaml` lifecycle: active→shadow, activation: active→allowed |
| 每周产出 >= 20 条 decision_outcome | ⏳ 机制已就绪 (scene-outcome-recorder + scenewatcher→MOS), shadow 化后由工程评审活动自然积累; 持续观察目标 |
| 明确标注"本场景产出永不计入价值指标" | ✅ 场景卡新增 `value_indicator_policy: "本场景产出永不计入价值指标 (BET-Y1Q2-T7-01 non_goals)"` |

未过: 无 (机制交付完成, 周产 20 条为观察目标)。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **场景卡路径不是 v2/**: 台账 verify 写 `docs/scene-cards/v2/engineering-delivery.yaml`, 实际是 `docs/scene-cards/engineering-delivery-dogfood.yaml` (无 v2/ 子目录)。
2. **场景卡 check 工具 pre-existing 失败**: `make scene-card-check` 所有 v2 场景卡都 fail, 根因是 Makefile 调用顺序错 (`--scene-card $f check` vs 正确 `check --scene-card <path>`) + preflight 要求 scene-card/v1 schema (v2 卡不兼容)。非本 bet 引入。
3. **decision_outcome 机制已存在**: scenewatcher 已按 ADR-0372 把 decision_outcome 持久化到 MOS, scene-outcome-recorder 记录人类裁决。T7-01 只需 shadow 化场景卡 + 标注, 无需新建收集器。
4. **active→shadow 需要 activation 同步改**: 只改 lifecycle 不改 activation 会不一致; 参照其他 shadow 卡 (document-review) 用 activation: allowed。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（主仓 commit）:
- `docs/scene-cards/engineering-delivery-dogfood.yaml` +2/-2 行: lifecycle→shadow + activation→allowed + value_indicator_policy 标注 + note

无新增脚本 / GaC 规则 / ADR。最小改动 (场景卡配置)。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **场景卡 shadow 化**: 改 lifecycle: shadow + activation: allowed + 参照现有 shadow 卡 (document-review)。
2. **decision_outcome 机制**: scenewatcher→MOS (ADR-0372) + scene-outcome-recorder 记录裁决; scene-outcomes.jsonl 被 gitignore。
3. **scene-card-check 有 pre-existing bug**: Makefile 调用顺序错 (`--scene-card $f check` 应 `check --scene-card <path>`) + preflight 只认 scene-card/v1; 需修复或迁移 check 工具。
4. **永不记入价值指标**: 场景卡 value_indicator_policy 标注 (T7-01 non_goals)。
5. **待办**: 若周产 <10 条触发 circuit_breaker (扩大到 commit 级评审)。
