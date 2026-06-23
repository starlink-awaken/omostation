---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
related: process/retrospectives/
note: "P53 R2 软收敛: retro/summary 命名文件交叉引用 process/retrospectives/, 沿用不动路径原则保留当前位置"
---
# Phase 3 Foundation Convergence Retrospective

> 日期: 2026-05-30
> 范围: `P3-WS3-GBRAIN-DEFAULT-ROUTE`, `P3-WS3-MINERVA-CLI-CONVERGENCE`, `P3-WS4-FRAGMENT-LLM-CLEANUP`, `P3-WS4-LLM-ENV-STANDARDIZATION`

## 1. 结果

本轮完成了 Phase 3 foundation 的第一批真实落地，而不是继续停留在 future-gated 规划：

| task_id | 结果 | 关键落点 |
|---------|------|----------|
| `P3-WS3-GBRAIN-DEFAULT-ROUTE` | done | `gbrain` 在 generic `LLM_*` 环境变量存在时，默认把 chat/expansion route 收敛到 `litellm:<model>`，并将 `LLM_BASE_URL/LLM_API_KEY` 注入 LiteLLM route seam |
| `P3-WS3-MINERVA-CLI-CONVERGENCE` | done | `minerva` CLI-facing config 现在接受 `LLM_PROVIDER/BASE_URL/API_KEY/MODEL`，不再只认 `OLLAMA_BASE_URL` |
| `P3-WS4-FRAGMENT-LLM-CLEANUP` | done | `ssot`、`ontoderive`、`metaos` 都接入 generic `LLM_*`，保留旧环境变量兼容 |
| `P3-WS4-LLM-ENV-STANDARDIZATION` | done | `.omo` 明确 Phase 3 foundation 的统一契约：`LLM_PROVIDER/LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` |

## 2. 代码证据

- `projects/gbrain/src/core/config.ts`
- `projects/gbrain/src/cli.ts`
- `projects/gbrain/test/config-env.test.ts`
- `projects/gbrain/test/ai/build-gateway-config.test.ts`
- `projects/kairon/packages/minerva/src/minerva/config.py`
- `projects/kairon/packages/minerva/tests/unit/test_config.py`
- `projects/kairon/packages/ssot/src/ssot_kernel/extractor/llm.py`
- `projects/kairon/packages/ssot/tests/test_extractor.py`
- `projects/kairon/packages/ontoderive/engine/intelligence/providers.py`
- `projects/kairon/packages/ontoderive/engine/intelligence/llm.py`
- `projects/kairon/packages/ontoderive/tests/test_llm.py`
- `projects/kairon/packages/metaos/src/metaos/layers/m_layer.py`
- `projects/kairon/packages/metaos/tests/test_unit.py`

## 3. 验证

已通过的最小验证：

1. `cd projects/gbrain && bun test test/config-env.test.ts test/ai/build-gateway-config.test.ts`
2. `cd projects/kairon/packages/minerva && PYTHONPATH=src python3 -m pytest tests/unit/test_config.py -q`
3. `cd projects/kairon/packages/ontoderive && python3 -m pytest tests/test_llm.py -q`
4. `cd projects/kairon/packages/ssot && PYTHONPATH=src python3 -m pytest tests/test_extractor.py -q`
5. `cd projects/kairon/packages/metaos && PYTHONPATH=src python3 -m unittest tests.test_unit.TestMLayer.test_ollama_backend_reads_standard_llm_env`

## 4. 复盘

### 4.1 这轮真正补齐了什么

1. **gbrain 不再只停留在“有 LiteLLM recipe”**：默认 chat/expansion route 现在可以从统一 `LLM_*` 入口收敛到 LiteLLM。
2. **Minerva / fragment 不再各玩各的 env 变量**：Phase 3 foundation 终于有了跨 repo 的统一入口。
3. **标准不只是文档**：统一 env 契约已经嵌入真实运行代码和测试，不再是孤岛规范。

### 4.2 仍然保留的边界

1. `metaos` 当前仍是 **Ollama-only backend**；本轮只让它接受统一 `LLM_*` 的 `ollama` 形态，没有把它直接改造成 LiteLLM/OpenAI backend。
2. `ssot` 和 `ontoderive` 现已支持统一 env 入口，但它们的 provider abstraction 仍偏轻量，后续如果要加 quota / routing / approval gate，最好继续向 provider-plane 对齐。
3. `.omo/tasks/blocked/` 中的 Apple / WeChat-SMB-Media 敏感规格依旧维持 blocked，不应被这轮 foundation 收敛误解成已解锁。

### 4.3 下一阶段建议

1. 以这轮 `LLM_*` 契约为底座，进入 Phase 3 capability track，而不是再回头做第二套 env 规范。
2. capability track 的第一批优先项建议继续保持：
   - `P3-T5-SKILL-ROUTER`
   - `P3-T4-MEMORY-TREE`
   - `P3-M3-CROSS-DOMAIN-RESEARCH`
3. 如果后续需要把 `metaos` 也切进 LiteLLM，应该新增显式 OpenAI-compatible backend，而不是继续复用 Ollama 探测逻辑。
