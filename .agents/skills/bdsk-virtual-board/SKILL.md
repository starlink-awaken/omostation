---
name: bdsk-virtual-board
description: "B.D.S.K. 虚拟董事会 4 角架构审议与真实 BOS/AetherForge 本地算力接入。用于高风险架构、技术取舍、跨仓协作和合规决策。"

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# B.D.S.K. Virtual Board

## 1. 何时使用

以下任务使用本技能：

- 系统架构、核心技术选型或跨仓协议变更；
- 高风险重构、数据主权、安全与合规审查；
- 需要在交付速度、长期维护、战略一致性和证据链之间做显式取舍。

B.D.S.K. 只提供审议建议，不替代 agent-workflow、测试、独立 review、人类 gate 或 GitHub branch protection。

## 2. 四角职责

| 角色 | 主要问题 |
|---|---|
| `@Builder` | 最小可落地实现是什么，依赖和回滚是否明确？ |
| `@Devil` | 哪些反例、滥用路径、单点和负 ROI 会推翻方案？ |
| `@Sage` | 方案是否推进北极星，是否引入第二真相或长期耦合？ |
| `@Keeper` | 声明、运行、证据、SSOT 和生命周期是否一致？ |

- `deep`：四角完整审议，适合架构与高风险变更。
- `fast`：缩短推理预算，但仍必须返回四角结构；不代表快速批准。

## 3. 唯一可执行链

```text
cockpit bdsk debate <low-sensitive-topic>
  -> bos://persona/bdsk/evaluate
  -> Agora persona_bdsk_evaluate
  -> bos://compute/aetherforge/infer
  -> python -m aetherforge.cli infer
  -> AetherForge running data plane / omlxc route
```

权威声明位于 `projects/agora/etc/bos-services.yaml`；Agora 的 POC service projection 必须与其一致。

禁止：

- Cockpit 或 BDSK 模块直连 Ollama、OpenAI-compatible HTTP 或模型 SDK；
- 新增第二个 BDSK persona URI、第二个 compute URI 或规则型“成功” fallback；
- 把静态模板、硬编码风险分、固定 `PROCEED` 或服务注册存在冒充真实推理；
- 把 AetherForge 不可用标成 AetherForge 已执行。

## 4. 调用与结果合同

```bash
cockpit bdsk debate "低敏、无凭证、无绝对路径的架构议题"
```

只有同时满足以下条件才是 `proof_state=proven`：

1. Cockpit 通过 `bos://persona/bdsk/evaluate` 调用 Agora；
2. Agora 通过 `bos://compute/aetherforge/infer` 得到结构化响应；
3. 响应包含 Builder、Devil、Sage、Keeper、风险分和建议；
4. 响应通过 allowlist/schema 校验，且标签与实际调用链一致。

任一环节不可用、超时、异常、结构错误或隐私拒绝时：

- `proof_state=not_proven`；
- `verdict=NOT_PROVEN`；
- CLI 非零退出；
- 不产生规则型意见、默认风险分、自动 ADR 或成功标签。

`REVIEW_REQUIRED` / `PROCEED_WITH_GUARDRAILS` 仍是建议，不是 commit、push、merge、部署或外发授权。BDSK 永不输出 `APPROVED` / `ACCEPTED` 作为执行许可。

## 5. 隐私边界

- 只提交低敏议题；不得包含绝对路径、凭证/token/API key、控制字符或超界正文。
- 明显敏感输入必须在 compute resolver 之前拒绝，resolver 调用次数为 0。
- 成功响应只返回 `topic_digest` 和必要的安全元数据，不回显 topic/context。
- 隐私负例只允许 mocked 测试；live smoke 使用随机低敏 nonce。
- 回执不得持久化 prompt、模型原始输出、绝对路径、凭证或底层错误正文。

## 6. 静态 shadow sandbox 的边界

`python bin/gac/bdsk-shadow-sandbox.py` 只是当前 diff 的有限文本模式扫描器：

- `STATIC_CLEAR` 表示未命中已登记模式，不表示运行时安全；
- `STATIC_FINDINGS` 表示发现需复核的静态模式；
- 两者都不调用 BDSK 模型，也不授权 commit、push、merge 或部署。

## 7. 落地门禁

1. 写入前执行 ADR-0203：`bootstrap -> start --bet -> claim`。
2. 先写 RED，覆盖 canonical URI、compute failure、隐私拒绝、无 fallback、无自动 ADR 和 CLI 非零退出。
3. live smoke 只用随机低敏 nonce；不可用必须保留 `not_proven` 和非零退出证据。
4. 子仓先独立 commit/tag/PR/CI/review，子 PR 合并后根仓 gitlink 才能指向对应 `origin/main` 合并 SHA。
5. BDSK 结果之后仍需 targeted tests、GaC/SSOT/reachability 和 author-external review；不得由 BDSK 自审代替。
