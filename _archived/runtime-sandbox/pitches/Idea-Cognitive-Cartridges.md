# 实现动态认知卡带 (Cognitive Frameworks)

> **Upstream**: 完善 eCOS 架构执行期能力 (Execution Adaptability)
> **Appetite:** 1小时

## 背景与上下文
根据我们此前的架构决议，C2G 的主干流转（Pitch -> Bet -> Task）必须保持固化和强依赖 M2 防腐层，不能做成复杂的 Workflow.yaml。

但是，对于具体的 Task 执行阶段，我们极其需要引入如 GSD (Get Shit Done)、Superpowers、OpenSpec 等外部优秀的工程方法论。为了在不破坏 C2G 链路的前提下做到这一点，我们需要在 `projects/ecos/src/ecos/ssot/mof/m1/cognitive_framework/` 目录下建立“认知卡带 (Cognitive Cartridges)”系统。

Agent 在接手 Task 时，可以根据 Task 上的标签或用户指定，动态加载对应的 YAML 卡带，从而改变其执行行为（例如要求输出特定的 PRD 格式，或采用 TDD 模式）。

## 核心目标
1. 在 M1 模型定义中建立 `cognitive_framework` 的基座 Schema。
2. 落地两个官方卡带范本：`gsd.yaml` (降本增效模式) 和 `superpowers.yaml` (大一统智能模式)。
3. 确保 C2G 不受影响。
