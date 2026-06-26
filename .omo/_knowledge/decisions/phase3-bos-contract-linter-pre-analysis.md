# BOS Contract Linter Phase 3 — 预部署分析与评估

> 日期: 2026-06-25
> 作者: omostation P110+ (Phase 3)
> 关联: 提案 paste_1.txt + paste_2.txt (BOS Contract Linter Phase 3: Autonomy 作战包 v1.0)
> 状态: ⚠️ Phase 3 **核心愿景成立但提案有 5 个严重问题**, 6 项必要调整

---

## 1. Phase 3 范围

| 交付物 | 文件 | 状态 | 评估 |
|:-------|:-----|:----:|:-----|
| **1. mof-contract-agent** | `projects/ecos/src/ecos/ssot/agents/mof_contract_agent.py` | 🆕 创建 | 路径新, agents/ 目录不存在 |
| **1b. agent 注册** | `projects/ecos/pyproject.toml` ([project.entry-points."qoder.agents"]) | ✏️ 增量 | qoder 框架**不存在**, 提案发明 |
| **2. /quest workflow** | `skills/quest/fix-bos-contract.yml` | 🆕 创建 | skills/ 目录**不存在**, 全新路径 |

**Phase 3 愿景**:
- 让 AI Agent 自主使用/诊断/修复 BOS 契约问题
- mof contract-lint 从工具 → "治理神经系统"
- /quest 实现"意图驱动开发" (Intent-Driven Development)

---

## 2. 前置条件检查 (5 项)

### 2.1 ✅ 满足的前置条件 (2/5)

| # | 条件 | 状态 | 证据 |
|:-:|:-----|:----:|:-----|
| 1 | Phase 2 v0.2 已实施 | ✅ | `mof_contract_lint.py` (546L, commit 4c1fc70f) |
| 2 | `--json` 输出结构化 | ✅ | agent 可对接真实数据, 不需 mock |

### 2.2 ❌ 不满足的前置条件 (3/5, 关键)

| # | 问题 | 影响 | 解决 |
|:-:|:-----|:-----|:-----|
| 3 | `projects/ecos/src/ecos/ssot/agents/` 目录不存在 | 提案 agent 路径需新建 | ✅ 创建 (mkdir -p) |
| 4 | `skills/quest/` 目录不存在 | 提案 workflow 路径需新建 | ✅ 创建 (mkdir -p) |
| 5 | qoder.agents 命名空间不存在 | 提案 entry-points 无对应框架 | **C1 调整**: 用 omo.agents 或 ecos.agents (匹配现有 ecosystem) |

---

## 3. 详细风险评估

### 3.1 高风险点 (5 个)

| # | 风险 | 触发条件 | 缓解措施 |
|:-:|:-----|:---------|:---------|
| **R1** | analyze_service() 返回 **mock 数据** 而非真实 subprocess 输出 | subprocess returncode=0 时, 走 hardcoded `{"direct_dependencies": ["bos://system/governance/status"], "affected_files": [...]}` | **C2 调整**: 解析真实 `--json` 输出 |
| **R2** | diagnose_error() 仅 2 个 error_id 字符串匹配 | "INTERNAL_MODULE_NOT_FOUND" / "INVALID_SCOPE" 之外的错误返回 `{"error": "Unknown error type."}` | **C3 调整**: 复用 v0.2 `explain_error` 函数 (4 个 ID 覆盖) |
| **R3** | /quest workflow "Propose edit" hardcoded 旧字符串 | `func_name: run_governance_audit_xxx` 不在真实 yaml 中, apply 无变化 | **C4 调整**: 用 Jinja2 模板 + 真实 error context |
| **R4** | qoder.agents entry-points 无对应框架 | qoder framework 不存在, agent 永远不会被调用 | **C1 调整**: 用 `ecos.agents` 或 `omostation.agents` (匹配现有 ecosystem) |
| **R5** | `entry_points` 配置在 pyproject 中, 但 hatchling 默认不支持 | 当前 ecos 没有 `[project.entry-points]` 块, 可能需要 hatch 配置 | ✅ hatch 默认支持 entry-points, 只需添加新块 |

### 3.2 中风险点 (2 个)

| # | 风险 | 触发条件 | 缓解措施 |
|:-:|:-----|:---------|:---------|
| **R6** | /quest workflow YAML 字段格式错误 (`inputSchema` / `phases` / `steps`) | 实际 runner (omostation quest handler) 可能不识别 | **C5 调整**: 验证现有 skills/ 模式 (无, 因 skills/ 不存在) |
| **R7** | agent `analyze_service` / `diagnose_error` 无 `--json` 集成 | agent 输出 text, 与 Phase 2 v0.2 `--json` 不对称 | ✅ 提案 agent 输出 JSON, 已正确 |

---

## 4. 投资回报 (ROI) 评估

### 4.1 量化收益

| 维度 | Phase 2 v0.2 | Phase 3 (with C1-C6) |
|:-----|:--------------|:------------------------|
| AI Agent 调用 | ❌ 无 | ✅ mof-contract-agent 通过 entry-points 注册 |
| 端到端修复 | ❌ 无 | ✅ /quest workflow diagnose→analyze→edit→validate→commit |
| 意图驱动 | ❌ 无 | ✅ "帮我修复这个" → AI 自动接管 |
| 错误诊断 (4 个 ID) | ✅ CLI `--explain` | ✅ Agent `diagnose_error` (复用 v0.2) |
| 影响分析 (12 mappings) | ✅ CLI `--impact` | ✅ Agent `analyze_service` (复用 v0.2 + JSON) |

### 4.2 工作量评估

| 任务 | 估时 |
|:-----|:----:|
| 创建 `ecos/ssot/agents/` + `mof_contract_agent.py` (C1-C3 调整后 ~120L) | 20 min |
| pyproject.toml `[project.entry-points."ecos.agents"]` 注册 | 5 min |
| 创建 `skills/quest/` + `fix-bos-contract.yml` (C4-C5 调整后 ~80L) | 20 min |
| 验证 (agent + workflow + Phase 2 回归) | 15 min |
| ADR + commit | 10 min |
| **合计** | **~70 min** |

### 4.3 ROI 评分

| 维度 | 评分 | 备注 |
|:-----|:----:|:-----|
| 实施风险 | 🟡 中 (R1-R5 高风险, 但都有 mitigation) |
| 实施工作量 | 🟢 中 (~70 min) |
| 长期价值 | 🟢 高 (闭环治理, 30 天作战包收官) |
| 与前两阶段兼容性 | 🟢 完全兼容 (复用 v0.2 `--explain`/`--impact`/`--json`) |
| **总评** | **🟢 值得执行 (with 6 调整)** |

---

## 5. 设计调整 (vs 提案, 6 项必要)

### 5.1 必要调整 (6 项)

| 编号 | 调整 | 原因 | 估时 |
|:-----|:-----|:-----|:----:|
| **C1** | entry-points 用 `ecos.agents` 而非 `qoder.agents` | qoder framework 不存在 | 1 min |
| **C2** | analyze_service() 解析 `--json` 输出而非 mock | mock 数据无价值 | 10 min |
| **C3** | diagnose_error() 内部 import v0.2 `explain_error`, 扩展到 4 个 ID | 提案 2 个 ID 覆盖不全 | 5 min |
| **C4** | /quest "Propose edit" 用真实 bos-services.yaml 字段 (无 hardcoded) | hardcoded 不在真实文件中, fix 无变化 | 15 min |
| **C5** | /quest workflow YAML 用 omostation 兼容格式 (基于现有 cockpit / hermes skill 模式) | 提案 YAML 字段可能不兼容 | 10 min |
| **C6** | 增加 --bos-yaml 参数传递 (agent 调用时显式指定) | 默认路径 CWD 敏感 (Phase 0 A4 教训) | 5 min |

### 5.2 analyze_service() 真实输出 (C2)

```python
def analyze_service(uri: str, bos_yaml: Path | None = None) -> dict[str, Any]:
    """Call mof contract-lint --json --impact and parse structured output."""
    cmd = ["uv", "run", "mof-contract-lint", "--impact", uri, "--json"]
    if bos_yaml:
        cmd.extend(["--bos-yaml", str(bos_yaml)])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="projects/ecos")
    if result.returncode not in (0, 1):  # 0=match, 1=no-mapping (still JSON)
        return {"error": f"subprocess failed: {result.stderr}"}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse failed: {e}", "raw": result.stdout[:200]}
```

### 5.3 diagnose_error() 复用 v0.2 (C3)

```python
from ecos.ssot.tools.mof_contract_lint import explain_error

def diagnose_error(error_log: str) -> dict[str, Any]:
    """Reuse v0.2 explain_error for 4 IDs (vs proposal 2)."""
    for error_id in ["INTERNAL_MODULE_NOT_FOUND", "INVALID_SCOPE",
                     "SCOPE_VALIDATION_SKIPPED", "ACTION_NAMING_CONVENTION"]:
        if error_id in error_log:
            text, _ = explain_error(error_id)
            return {"error_id": error_id, "explanation": text,
                    "suggested_fix": _extract_fix_from_text(text)}
    return {"error": "Unknown error type", "hint": "use --explain for known IDs"}
```

### 5.4 /quest workflow (C4-C5)

```yaml
name: fix-bos-contract
description: Diagnose and fix BOS Contract errors via mof-contract-agent.
inputSchema:
  type: object
  properties:
    error_log:
      type: string
      description: Raw error log from `mof contract-lint`.
    uri:
      type: string
      description: The affected BOS URI (e.g., bos://governance/omo/audit).
    yaml_path:
      type: string
      default: projects/agora/etc/bos-services.yaml
  required: [error_log, uri]

phases:
  - title: Diagnose
    steps:
      - name: Run diagnosis
        tool: Bash
        args:
          command: |
            uv run mof-contract-agent diagnose "{{ args.error_log }}"

  - title: Analyze Impact
    steps:
      - name: Get impact
        tool: Bash
        args:
          command: |
            uv run mof-contract-agent analyze "{{ args.uri }}" --bos-yaml "{{ args.yaml_path }}"

  - title: Generate Fix
    steps:
      - name: Read YAML
        tool: Read
        args: { file_path: "{{ args.yaml_path }}" }
      - name: Propose edit (template-driven, no hardcoded strings)
        tool: Agent
        args:
          subagent_type: mof-contract-agent
          prompt: |
            Based on diagnosis + impact, propose precise YAML edit for
            URI {{ args.uri }} in {{ args.yaml_path }}.

  - title: Validate & Commit
    steps:
      - name: Re-lint
        tool: Bash
        args:
          command: cd projects/ecos && uv run mof contract-lint --bos-yaml "../{{ args.yaml_path }}"
      - name: Commit
        tool: Bash
        args:
          command: |
            git add {{ args.yaml_path }} && \
            git commit -m "fix(bos): resolve {{ args.uri }} via /quest fix-bos-contract"
```

### 5.5 不在 Phase 3 范围内 (Phase 3+)

- 真实 AI Agent runtime (Plan, Engineer, Graphify) 调用 mof-contract-agent
- /quest runner (omostation quest handler) 解析 workflow YAML
- Skills discovery (agent 找到 fix-bos-contract skill)
- 端到端 Autonomy Review (提案要求)

**Phase 3 范围内**: 提供 agent + workflow 文件, 满足"可注册 + 可发现"
**Phase 3 范围外**: 实际 agent 调用 + workflow 触发 (需 omostation runtime 配合)

---

## 6. 执行计划 (Phase 3)

### 6.1 顺序依赖

```
Step 1: 创建 agents/ 目录 + mof_contract_agent.py (C1-C3 调整后)
   ↓ (无依赖)
Step 2: pyproject.toml 注册 [project.entry-points."ecos.agents"]
   ↓ (依赖 Step 1)
Step 3: 创建 skills/quest/ + fix-bos-contract.yml (C4-C5 调整后)
   ↓ (无依赖)
Step 4: 验证 (agent CLI + workflow YAML 语法 + Phase 2 回归)
   ↓ (无依赖)
Step 5: ADR + commit + mof-version
```

### 6.2 关键决策

| 决策 | 选择 | 理由 |
|:-----|:-----|:-----|
| entry-points 命名空间 | **`ecos.agents`** (非 qoder.agents) | qoder framework 不存在, ecos 自有 agent 命名 |
| analyze_service 数据源 | **真实 `--json` 输出** | mock 无价值, 复用 v0.2 |
| diagnose_error 数据源 | **真实 v0.2 `explain_error()`** | 4 IDs 覆盖 (vs 提案 2) |
| /quest YAML 格式 | **简化 omostation 兼容** | 避免引入未支持的字段 |
| hardcoded 旧字符串 | **完全去除** | 用模板驱动 + Agent 提议 |

---

## 7. 验证清单

| 验证项 | 期望 |
|:-------|:-----|
| `mof-contract-agent analyze bos://governance/omo/audit --bos-yaml ...` | 输出真实 JSON (含 deps + files) |
| `mof-contract-agent diagnose "INTERNAL_MODULE_NOT_FOUND..."` | 输出 4-ID 覆盖的错误诊断 |
| `mof-contract-agent diagnose "XYZ_UNKNOWN..."` | 返回 `{"error": "Unknown error type"}` |
| `uv pip install -e projects/ecos` 后 `mof-contract-agent` 可调用 | ✅ |
| pyproject.toml `[project.entry-points."ecos.agents"]` | ✅ 注册成功 |
| skills/quest/fix-bos-contract.yml YAML 语法 | ✅ yaml.safe_load 通过 |
| Phase 2 回归 (`mof-contract-lint --explain/--impact`) | ✅ 行为不变 |
| dashboard 22/22 OK | ✅ |

---

## 8. 跨阶段影响

### 8.1 Phase 0 → Phase 1 → Phase 2 → Phase 3 衔接

| 阶段 | 状态 | 贡献 |
|:-----|:----:|:-----|
| Phase 0 v0.1 | ✅ | 基础工具 (4 模式 CLI) |
| Phase 1 | 🔲 待 | CI / system health / l4-kernel monitor (与 Phase 3 独立) |
| Phase 2 v0.2 | ✅ | `--explain` + `--impact` 智能增强 |
| **Phase 3** | 🔲 实施 | **Agent + Workflow 自治化** |

### 8.2 Phase 3 与 omostation runtime 关系

- **Phase 3 范围内**: 创建 `mof-contract-agent` + `/quest` workflow
- **Phase 3 范围外**: 
  - omostation quest handler 解析 workflow YAML
  - AI Agent runtime 调用 `mof-contract-agent`
  - Skill discovery (agents 找到 fix-bos-contract)
  - 端到端 Autonomy Review

**Phase 3 是基础设施 (infrastructure)**, runtime 集成是 Phase 4+ 工作。

---

## 9. 决策建议

### 9.1 ✅ 推荐执行 Phase 3 (with 6 调整)

理由:
1. **核心愿景成立**: Agent + Workflow 是 30 天作战包收官的关键
2. **6 调整明确**: 每项都有具体 mitigation, 不偏离 Phase 3 目标
3. **复用 Phase 2 v0.2**: analyze_service / diagnose_error 直接调用 `--json` + `explain_error()`, 无重复实现
4. **基础设施价值**: 即使 Phase 3+ 不实施 runtime 集成, agent + workflow 文件本身就是有价值的基础设施

### 9.2 实施前需确认

| 问题 | 决策 |
|:-----|:-----|
| 是否新增 ADR? | ✅ 是 (ADR-0107) |
| 是否升级 mof-version? | ✅ 是 (v0.0.101 → v0.0.102) |
| skills/ 目录是否属于 omo governance? | 🔲 需用户确认 (本 ADR 假设是) |
| 是否同步 Phase 1 (CI/health)? | ❌ 推迟 (与 Phase 3 独立) |

### 9.3 不推荐执行

- ❌ 跳过 C2 (mock 数据) — agent 无价值
- ❌ 跳过 C3 (2 个 ID) — 覆盖率不足
- ❌ 跳过 C1 (qoder.agents) — 命名空间无对应 framework
- ❌ 推迟 Phase 3 — 30 天作战包未闭环

---

## 10. 批准

✅ **本分析建议执行 Phase 3 (with 6 调整)**

**预计产出**:
- `mof_contract_agent.py` (~120L, 复用 v0.2)
- `[project.entry-points."ecos.agents"]` 注册
- `skills/quest/fix-bos-contract.yml` (~80L, 模板驱动)
- ADR-0107 (Phase 3 决策)
- mof-version: v0.0.101 → v0.0.102

**实施时间**: ~70 分钟
**风险**: 中 (5 高风险 mitigation 充分, 但仍有 proposal 假数据/假路径风险)

---

*版本: v1.0 | 2026-06-25 | Phase 3 预部署评估完毕*
