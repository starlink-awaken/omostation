---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0193: Domain Policy-as-Code 业务规则引擎与公文红线治理架构

- **状态**: `ACCEPTED`
- **日期**: 2026-08-17
- **作者**: Sage (战略家) & Builder (建造者)
- **关联架构**: MOF SSOT L0, ADR-0190, ADR-0191, ADR-0192

---

## 1. 背景与业务痛点 (Context & Problem)

在卫健委信息化与国转中心科技成果转化的业务场景中，Agent 协助拟定公文、项目方案或申报立项时，存在违反行业监管与国有资产法规红线的风险：
1. **卫健委重大信息化项目红线**：根据《政务信息化项目建设管理办法》，单体预算超过 500 万元的项目必须经过专家评审论证；核心临床业务与全民健康信息平台必须具备网络安全等保三级与信创自主可控标准。
2. **科技成果转化团队收益红线**：根据《促进科技成果转化法》及国家科技部政策，科研团队在成果转让、许可或作价入股中的收益分配比例不得低于 70%；中试与产业化项目的技术成熟度 (TRL) 原则上需达到 ≥6 级。

过去这些规则依赖人工后期复核，容易造成合规漏洞。

---

## 2. 架构设计与决策 (Decision & Architecture)

建立 **Policy-as-Code 业务规则引擎**，作为 MOF SSOT 治理体系的业务级扩展：

```mermaid
graph TD
    Proposal[业务方案/公文/需求文本] --> PolicyInspector[PolicyComplianceInspector]
    PolicyInspector --> RuleWJ1[E-POL-WJ-001: 卫健委预算超限需论证]
    PolicyInspector --> RuleWJ2[E-POL-WJ-002: 核心系统等保三级与信创]
    PolicyInspector --> RuleTF1[E-POL-TF-001: 成果转化团队收益≥70%]
    PolicyInspector --> RuleTF2[E-POL-TF-002: 产业化TRL准入≥6]
    PolicyInspector --> AuditReport[PolicyAuditReport (JSON/CLI)]
    AuditReport --> FastMCP[FastMCP runtime_domain_compliance_audit]
    AuditReport --> CLI[ecos-constraint policy audit]
```

### 核心规则定义

| 规则编号 | 适用领域 | 严重级别 | 规则约束与红线 | 处置建议 |
|:---|:---|:---|:---|:---|
| **`E-POL-WJ-001`** | `work-weijian` | `BLOCK` | 预算 >500 万元必须包含专家论证并采购信创自主可控软硬件 | 组织专家论证会并补充信创技术架构评估报告 |
| **`E-POL-WJ-002`** | `work-weijian` | `BLOCK` | 涉及医疗/临床数据平台必须明确网络安全等保三级与互联互通标准 | 方案必须包含等保三级测评方案与国密标准 |
| **`E-POL-TF-001`** | `work-transfer` | `BLOCK` | 科技成果完成团队收益分配比例不得低于 70% | 调整分配方案至团队占比 ≥70% |
| **`E-POL-TF-002`** | `work-transfer` | `WARN` | 产业化/中试落地项目建议技术成熟度 TRL ≥ 6 | 补充中试验证报告或先开展概念验证 (PoC) |

---

## 3. CLI 与 MCP 接口 (Interfaces)

```bash
# 审计方案文件或输入文本
ecos-constraint policy audit <file_or_text> [--domain work-weijian|work-transfer] [--strict]

# 查看规则解释与动机
ecos-constraint policy explain E-POL-WJ-001

# 列出所有业务规则
ecos-constraint policy list
```

**FastMCP 工具**：
- `runtime_domain_compliance_audit(target_text_or_path: str, domain: str = "auto") -> dict`

---

## 4. 验证与成果 (Validation)

- 单测全部覆盖 4 项核心业务规则的拦截与放行。
- 集成至 `runtime` FastMCP 工具链，供 Agent 在生成公文或方案时实时自检。
