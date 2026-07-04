# BOS / MCP / GaC 注册全面审计报告

> **日期**: 2026-07-04
> **审计员**: laowang-engineer
> **范围**: 最近 5 天变更 vs agora MCP/BOS 注册面 + GaC 执行链 + 文档同步
> **方法**: evidence-smoke 量化 + 注册表三方对账 + git diff 取证
> **关联**: 本次审计驱动的落地 PR = work/omlx-gac-audit-closure

---

## 1. 总体健康度（evidence-smoke 量化）

| 维度 | 状态 | 证据 |
|------|------|------|
| **BOS 声明/执行鸿沟** | 🟢 **0** | 115 声明 / 113 resolve / resolve率 0.983 / 2 deprecated（调研中，expires 2026-07-25） |
| **evidence_health_score** | 🟢 **99.0/100** | `.omo/_delivery/evidence-smoke/2026-07-04.json`（对比假的 health_score=100） |
| **transport 分布** | 🟢 stdio 58 / mcp_stdio 37 / internal 20 | 标签口径已从旧 `mcp` → `mcp_stdio` 修正 |
| **反馈回路** | 🟢 存活 | governance 最后 2026-07-04T01:04:26Z，停摆 0.0h |
| **doc-ssot-lint** | 🟢 ok=true | 113 files / 0 conflicts |
| **GaC 声明/执行** | 🔴 **鸿沟** | 见 §3 P0（声明合法但 mesh_routing/memory_rag 无执行实现） |

**结论**: BOS 层真绿（鸿沟 0），但 GaC 执行层存在声明/执行鸿沟（同 evidence-smoke 治的 BOS 鸿沟一类）。

---

## 2. 注册面盘点

### 2.1 BOS 服务注册（`projects/agora/etc/bos-services.yaml`，971 行 / 115 条）

| 域 | 条数 | 域 | 条数 |
|----|------|----|------|
| governance | 25 | persona | 8 |
| capability | 25 | ecos | 8 |
| analysis | 23 | system | 7 |
| memory | 14 | swarm/runtime/omo/meta/l4-kernel/cockpit | 各 1 |

### 2.2 BOS 未实现跟踪（`projects/agora/etc/bos-unimplemented.yaml`，17 条）

`last_reviewed: 2026-06-28`（6 天前，建议复审）。条目复核结果见 §3 P2。

### 2.3 MCP server 注册（`projects/agora/src/agora/registry.yaml`）

minerva-deep-research（5 tools）/ ontoderive-engine / agentmesh-gateway 等已注册。

### 2.4 调度注册（`.omo/_truth/registry/services.yaml`，4 条）

governance.watch / evidence-smoke / compass-radar / gen-service-configs（launchd 调度，从注册生成 plist，非 BOS）。

---

## 3. 发现清单（分级）

### 🔴 P0 — GaC 声明/执行鸿沟（治本需专项）

**现象**: governance-checks.yaml 登记了 3 个新 CR，gac-validate/gac-drift 报绿（声明合法），但 check_type 缺执行实现：

| CR | check_type | target | executor | 执行实现 |
|----|-----------|--------|----------|---------|
| CR-OMLX-MESH-ROUTING-01 | mesh_routing | bin/gac-mesh-router.py | [omo_audit, ci_gate] | ❌ target 是 HTTP server，非自检脚本 |
| CR-KOS-EPIGENETIC-RAG-01 | memory_rag | bin/gac-consensus-inject.py | [omo_audit, ci_gate] | ❌ 无验证逻辑 |
| CR-AETHERFORGE-ONBOARD-INTEGRITY-01 | ssot_lint | bin/gac-compute-onboard.py | [omo_audit, ci_gate] | ⚠️ ssot_lint 有执行体（doc-ssot-lint 系列），可能可执行 |

**根因（GaC 架构厘清）**:
- `gac-validate.py` / `gac-drift.py` 是 **meta-gate**（校验 CR 字段完整 / executor 在 EXECUTOR_ENUM / target 存在），**不是执行器**
- `executor: [omo_audit, ci_gate]` 是声明"归这俩通道管"，实际执行由 omo audit / CI 编排
- `check_type` 是分类标签，**mesh_routing/memory_rag 无对应执行 script**（rg 仅找到 GAC-RULE-*.yaml 声明 + m2 schema，无 .py 执行体）

**影响**: GaC 报绿是"声明合法"层绿，非"执行到位"层绿。与 evidence-smoke 治的 BOS 鸿沟同构。

**Follow-up（专项，非本次 PR 范围）**:
1. 给 GaC 加执行鸿沟量化（类似 evidence-smoke：声明 CR vs 各 executor 通道实际执行的 CR）
2. 或为 mesh_routing/memory_rag 写执行实现（验证"跨节点 LLM 是否走 :7435" / "RAG 是否 TF-IDF Top-2 注入"）

---

### 🔴 P1 — omlx 工作树裸奔（本次 PR 落地）

**现象**: 主仓工作树 8 项 omlx 改动未落盘（auto-sync 抹平 / 换机即丢）：

| 文件 | 状态 | 内容 |
|------|------|------|
| bin/gac-compute-onboard.py | untracked (218行) | 5 大算力通道审计（cc-switch/codexbar/models/litellm/omlxc） |
| bin/omlxc-node-wakeup.py | untracked (99行) | AetherForge 从机 WoL 唤醒代理 |
| bin/gac-consensus-inject.py | dirty | embedding 超时 30s→1s（RAG 按需注入不卡 gate） |
| bin/gac-ingress-check.py | dirty | +select stdin 非阻塞 + LLM 超时 1s |
| bin/matrix-consistency-lint.py | dirty | port key `str(k)` 类型对齐（11434 int/str 漏判修复） |
| .omo/_truth/registry/governance-checks.yaml | dirty (+13) | 新增 CR-AETHERFORGE-ONBOARD-INTEGRITY-01 |
| protocols/port-registry.yaml | dirty (+1) | +11434 ollama |
| docs/project-registry.yaml | dirty (+6) | +compute_nodes lan_ip/mac + aetherforge layer X→L2 |

**⚠️ 关键纠缠（落地阻塞，需决策）**:

主仓工作树 omlx dirty **深度依赖本地 main 90e52736 的 3 个 agent commit（843 行主体）**：
- `bf29098d` feat(ecos-v6): Phase A+B RAG TF-IDF + C2G ingress（governance-checks +167 / gac-consensus-inject +220 / gac-ingress-check +271）
- `9541f77d` chore(governance): update X1-X4, L0 constraints, eCOS v6 GaC rules
- `90e52736` chore(governance): integrate AetherForge L0 + CR-KOS-ONTOLOGY-DRIFT-01（bump ecos → 190d9e7）

这 3 个 commit **未 push 到 origin/main**（origin/main = 6f0578a5，干净）。dirty 补丁的 context（如 CR-KOS-EPIGENETIC-RAG-01）在这 3 个 commit 里，**不能 apply 到 origin/main**。

**结论**: 本次 PR 必须基于 90e52736（含 3 agent commit + 补丁），不能拆成独立 clean PR。落地 = push 整坨。

---

### 🟡 P2 — bos-unimplemented 复审（条目有效，仅日期旧）

**验证结论（2026-07-04）**:
- `bos://analysis/minerva/draft|audit`：minerva cli.py 无 draft 子命令，audit 是查 log 非 serve → **条目仍有效，不减**
- `bos://analysis/ontoderive/audit|fact-check`：ontoderive cli.py 无 audit/fact-check 子命令，MCP 已实现但未暴露此 tool → **条目仍有效，不减**
- `persona/health-profile`：包 `kairon/packages/health-profile/`（连字符）**实际存在**（有 models.py/io.py，无 cli.py）→ **非死条目**，summary/alert 待实现合理

**Follow-up**: 仅需更新 `last_reviewed: 2026-06-28 → 2026-07-04`（轻量，本次未改避免 agora 子模块 push 纠缠，留作下次 agora PR 顺带）。

---

### 🔴 P3 — ecos gitlink 悬空（pre-existing，阻塞 CI）

**现象**:
- 本地 main 90e52736 的 ecos gitlink = `190d9e7`（领先 ecos origin/main 2 commit：190d9e7 + 79d5ed7）
- `git -C projects/ecos branch -r --contains 190d9e7` = **空**（未 push 到任何 remote）
- origin/main（6f0578a5）的 ecos gitlink = `184bca4`（✅ 可达）

**影响**: 任何含 90e52736 ecos bump 的 PR，CI `submodule-reachability-gate` 必红（190d9e7 不可达）。这是 3 个 agent commit 未 push 的根因之一。

**解法**: push ecos `190d9e7 + 79d5ed7` 到 ecos origin（完成的 MOF feature，非 WIP）。

---

### 🟡 P4 — agent 本地 commit 未 push（纪律问题）

本地 main 领先 origin/main 3 commit（90e52736/9541f77d/bf29098d，843 行）。Phase 2c blocking pre-push 守住 direct push main，但 agent 仍本地 commit 累积。配合 P3 ecos 悬空，形成"commit 了 push 不上去"的死锁。

---

## 4. 绿灯清单（已正确闭环）✅

- `bos://memory/kos/mcp-server` 已注册并 resolve（agora 2f1ad65，KOS 统一 MCP 入口，SGF-v1 硬件外挂）
- `gac-mesh-router.py` 全链登记：x1-policy:202 + x3-value:193 + x4-consistency:170 + CR-OMLX-MESH-ROUTING-01 + port 7435（port-registry:6 已入库）
- `gac-compute-onboard.py` 走 agent-workflow（events.jsonl:130,137 有 claim/close 证据）
- port 7435（omlx-mesh-router）已在 port-registry（x4 规则满足）
- CALLCHAIN 文档只提 7 bos:// → doc-ssot-lint 判 ok（navigation 文档契约允许不全列）
- health-profile 包实际存在（修正"死条目"误判）

---

## 5. 本次落地范围（PR work/omlx-gac-audit-closure）

**✅ 落地（独立补丁，base origin/main 6f0578a5，不依赖 90e52736）**:
- bin/gac-compute-onboard.py（新）：5 大算力通道并网自检
- bin/omlxc-node-wakeup.py（新）：AetherForge 从机 WoL 唤醒
- bin/matrix-consistency-lint.py（fix）：port key str(k) 类型对齐
- protocols/port-registry.yaml：+11434 ollama
- docs/project-registry.yaml：+compute_nodes lan_ip/mac + aetherforge layer X→L2
- 本审计报告

**🔴 Blocked（依赖本地 90e52736 agent commit，需整坨 push，本次不含）**:
- bin/gac-consensus-inject.py（embedding 超时 30s→1s）— context 在 90e52736 RAG TF-IDF (+220行)
- bin/gac-ingress-check.py（+select stdin + LLM 超时）— context 在 90e52736 C2G ingress (+271行)
- .omo/_truth/registry/governance-checks.yaml（+CR-AETHERFORGE-ONBOARD-INTEGRITY-01）— context 在 90e52736 (+167行)

**解 block 前置（push 90e52736 整坨前必修，否则 CI 全红）**:
1. 生成 docs/generated/agent-gac-rules.md digest（AGENTS.md 引用，90e52736 未生成）
2. 验 scripts 子模块含 check-doc-ssot-snapshots.py（gitlink 579af0b 两边一致，worktree init 缺失为环境假阳性，origin/main 实际有）
3. push ecos 190d9e7+79d5ed7 到 ecos origin（解 P3 悬空）

**降级为 Follow-up**:
- P0 GaC 执行鸿沟（专项，需执行实现或鸿沟量化）
- P2 bos-unimplemented last_reviewed 更新（轻量，下次 agora PR 顺带）

---

## 6. Follow-up 清单

| ID | 项 | 优先级 | 责任 |
|----|----|--------|------|
| FU-1 | GaC 执行鸿沟量化（声明 CR vs executor 实际执行） | P0 专项 | governance-team |
| FU-2 | mesh_routing/memory_rag 执行实现 | P0 专项 | governance-team |
| FU-3 | bos-unimplemented last_reviewed 更新 + 复审节奏常态化 | P2 | agora-team |
| FU-4 | agent 本地 commit push 纪律（配合 ecos bump 完整性） | P1 纪律 | all-agents |
