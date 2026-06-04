# Workspace 项目资产清单

> 生成: 2026-06-04
> 性质: live inventory snapshot
> 原则: 以当前工作树和可复算目录结果为准；历史文档和旧阶段报告只作候选证据，不作真相源

---

## 概览

| 维度 | 当前事实 |
|------|----------|
| 根仓库 | `omostation` workspace root |
| 当前 `projects/` 可见项目 | `kairon`, `gbrain`, `agentmesh`, `hermes-console`, `_archived` |
| `kairon` 活跃 Python 包 | **25** |
| `agentmesh` 状态 | 已归档壳，README 声明能力已迁入 `kairon` |
| `SharedBrain` 状态 | 当前 `projects/` 树中**不存在独立 sibling repo** |
| `.omo` 角色 | 治理与证据层，不应替代 repo 侧 live inventory |

---

## 一、kairon — 知识工程与研究栈（25 包）

> 位置: `projects/kairon/`
> 构建: `uv` workspace
> 说明: 当前 checkout 可见 25 个带 `pyproject.toml` 的包

### 1.1 当前活跃包

- `agent-runtime`
- `agora`
- `codeanalyze`
- `core-models`
- `cron-service`
- `ecos`
- `eidos`
- `engine-core`
- `forge`
- `iris`
- `kairon-assistant`
- `kairon-voice`
- `kaironcloud-billing`
- `kos`
- `kronos`
- `llm-gateway`
- `metaos`
- `minerva`
- `ontoderive`
- `shared-lib`
- `sharedbrain-bridge`
- `sophia`
- `ssot`
- `symphony-protocol`
- `wksp`

### 1.2 重要说明

- `packages/` 目录必须只容纳包成员；运行期 DB、分析产物、临时文件不应放在这里。
- `core-models` 是当前最明确的依赖基座，但不能单靠它解释整体运行时架构。
- `wksp` 是否为统一 operator-home，必须以 repo 侧运行和文档契约确认，不能靠历史叙述默认成立。

### 1.3 当前已知漂移风险

- 历史资料常写 `26/31` 包，这与当前 checkout 不符。
- 近期 git 历史和旧文档仍引用过以下当前树中不存在的包名：
  - `agent-hub`
  - `eu-pricing`
  - `gc-engine`
  - `observability`
  - `pontus`
  - `sharedbrain-standalone`

---

## 二、agentmesh — 已归档接缝项目

| 属性 | 当前事实 |
|------|----------|
| 位置 | `projects/agentmesh/` |
| 状态 | 归档壳 |
| 当前角色 | 保留迁移声明和归档入口，不再视为主开发面 |
| 风险 | README 中曾把 Agent Registry 指向 `packages/agent-hub/`，但当前 `kairon` checkout 未见该包 |

---

## 三、gbrain — 知识脑

| 属性 | 当前事实 |
|------|----------|
| 位置 | `projects/gbrain/` |
| 技术栈 | TypeScript / bun |
| 状态 | 活跃 |
| 角色 | 独立知识捕获与检索能力面，和 `kairon` 通过场景/桥接契约协同 |

---

## 四、hermes-console

| 属性 | 当前事实 |
|------|----------|
| 位置 | `projects/hermes-console/` |
| 状态 | 独立项目，待进一步架构对齐评估 |

---

## 五、_archived

| 属性 | 当前事实 |
|------|----------|
| 位置 | `projects/_archived/` |
| 角色 | 历史项目和迁移资料归档区 |
| 注意 | 归档内容可作迁移证据，不应默认代表 live capability |

---

## 六、治理约束

1. repo 内当前结构优先于 `.omo` 历史叙述。
2. `.omo` 只登记 live evidence、task、closeout，不复制 repo 正式报告正文。
3. 任何包数、项目边界、迁移状态，都应能被目录扫描或测试输出复算。
