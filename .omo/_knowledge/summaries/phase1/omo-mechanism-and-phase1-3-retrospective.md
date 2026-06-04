# OMO mechanism and Phase 1-3 retrospective

> 日期: 2026-05-31
> 范围: `.omo` 机制本身 + Phase 1 / Phase 2 / Phase 3 的连续复盘

## Mechanism retrospective

`.omo` 的演进路径已经比较清晰：

1. **最初阶段** 更像文档仓库，结构可读但缺少执行闭环。
2. **治理阶段** 引入 goals / state / tasks / workers / standards，形成控制面雏形。
3. **执行阶段** 通过 provider plane、worker dispatch、Phase 3 acceptance runner，把“治理设计”落成“可执行机制”。
4. **融合阶段** 再通过四平面入口，把底层机制统一成可理解、可导航、可验证的 operating model。

这一轮最大的收获不是多了几个 INDEX，而是明确了：**导航层可以升级，但底层 SSOT 不能漂移。**

## Phase 1 retrospective

Phase 1 的核心价值是打底：

- 建立基础设施、集成环境、初始测试矩阵。
- 证明系统能够通过烟雾、E2E、故障注入、性能基线。
- 形成“先验证再推进”的基础纪律。

Phase 1 的不足也很明显：治理信息仍较分散，很多结论依赖人工阅读长文档才能恢复上下文。

## Phase 2 retrospective

Phase 2 的核心价值是把治理机制真正接到运行时：

- provider plane、LiteLLM route seam、agent runtime wiring 被真实打通。
- `.omo` 不再只描述计划，而开始回写真实状态、任务、证据。
- 安全边界和 blocked specs 被明确保留，没有为了“完成率”强行越界。

Phase 2 的不足是：机制已经存在，但入口层和认知层仍不够统一，容易出现“知道机制的人会用，不知道的人找不到”的问题。

## Phase 3 retrospective

Phase 3 的核心价值是完成从 foundation 到 capability 再到 acceptance 的闭环：

- 统一 `LLM_*` contract，消除了多仓库的 provider/env 碎片化。
- 落地 capability slice，把 KOS / Minerva / MetaOS / Iris / gbrain 的关键能力串起来。
- 用 `scripts/phase3_acceptance.py` 把 wksp orchestration、capability、recovery 统一成一个 acceptance baseline。

Phase 3 最重要的结果，是让 `.omo` 第一次拥有了**可以重复执行的完成态验证**。

## Cross-phase pattern

回头看 Phase 1-3，有一个稳定模式：

- **Phase 1** 解决“能不能跑”
- **Phase 2** 解决“怎么受控地跑”
- **Phase 3** 解决“怎么证明它真的完成了”

而四平面融合解决的是下一层问题：**怎么让这些能力长期可理解、可维护、可扩展。**

## What improved in this round

这次进一步融合升级，主要补上了三点：

1. **战略层**：明确四平面是 `.omo` 的长期 operating model，而不是一次性文档重构。
2. **战术层**：明确 control / truth / knowledge / delivery 的写入边界和职责边界。
3. **执行层**：新增蓝图与总复盘，并用测试约束它们必须挂到顶层入口与知识面索引。

## Next evolution priorities

1. **Phase 4 以前，先守住机制边界**：新增内容先判平面，再写入底层位置。
2. **优先做验证自动化，而不是继续扩文档树**：避免再次回到“目录更大、机制更松”的状态。
3. **把 Phase 1-3 的成果视为 baseline，而不是历史包袱**：后续 roadmap 直接以这些能力为默认前提。

## Final assessment

这套 `.omo` 机制目前已经从“计划与说明中心”升级成“治理、执行、验证、复盘一体化的操作台”。

它接下来最需要的不是更多机制，而是：

- 继续守住 SSOT 不漂移；
- 继续让关键命令可验证；
- 继续让阶段经验进入 knowledge/process，而不是散失在会话里。
