---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-10-17
---
# 文档治理提炼与蒸馏（2026-10-14）

## 一、背景

在本轮工作中，我们系统性地修复了文档治理元数据问题。最初文档治理检查发现大量文档存在元数据不一致（status/lifecycle/frontmatter 缺失或取值非法），经过系统性修复后，文档治理检查从警告状态收敛到符合预期。

## 二、目标

本轮“提炼和蒸馏环节”的目标是：系统性提炼本次文档治理修复经验，固化为可复用的工具、记忆、技能和操作指南，处理剩余警告，并产出可直接复用的沉淀成果。

## 三、已完成工作

### 3.1 初始修复（PR #4767 合并）
- 修复 126 个文件的文档治理元数据问题
- 统一 status 映射：`closed/done/candidate/completed/final/accepted/proposed/milestone/blocked` → `archived`
- 统一 lifecycle 映射：`signal→spec`、`planning→plan`、`redirect→history`、`stable→ssot`、`derived/active/production→entry`、`evidence→history`
- 补充缺失的 frontmatter 字段（schema、status、lifecycle、owner、last-reviewed、type）
- 更新过期的 `last-reviewed` 日期

### 3.2 剩余警告处理
- 处理 `resident-retro-candidate/v1` 等自定义 schema 文件的特殊情况
- 正确处理 frontmatter YAML 结构（保留原有字段，如 topic、generated_at、counts 等）
- 修复 malformed_frontmatter 问题

## 四、提炼的模式总结

### 4.1 Status 映射规则
| 原始值 | 映射值 | 说明 |
|---|---|---|
| closed, done, completed, final | archived | 已完成的历史文档 |
| candidate, accepted, proposed, milestone | archived | 已定稿/归档状态 |
| blocked | archived | 回顾文档中标记为阻断的历史记录 |

### 4.2 Lifecycle 映射规则
| 原始值 | 映射值 | 说明 |
|---|---|---|
| signal | spec | 信号类文档映射为规范 |
| planning | plan | 规划类映射为计划 |
| redirect | history | 重定向类映射为历史 |
| stable | ssot | 稳定类映射为单一事实源 |
| derived, active, production | entry | 派生/活跃/生产映射为条目 |
| evidence | history | 证据类回顾文档映射为历史 |

### 4.3 不同 schema 的处理差异
- **md/v1**：标准 Markdown 文档，需补全 status、lifecycle、owner、last-reviewed、type
- **bet-retro/v1**：BET 回顾文档，通常已有 bet_id 等字段，重点修复 status/lifecycle
- **resident-retro-candidate/v1**：自动生成的 resident 回顾候选文档，需保留 topic、generated_at、counts 等原有字段，同时补全治理必需字段

## 五、可复用资产

### 5.1 全局记忆（已沉淀）
- `doc_governance_fix_patterns_and_mappings`：记录了完整的映射规则和修复模式
- `remaining_doc_governance_warnings`：记录了剩余警告的处理方式和经验

### 5.2 全局技能（已沉淀）
- `apply_doc_governance_fixes_programmatically`：可复用的文档治理修复技能，封装了读取 findings、应用映射、验证修复的逻辑

### 5.3 工具脚本
- `bin/ssot/doc-governance-autofix.py`：现有的自动修复脚本，支持 dry-run/apply
- `bin/ssot/doc-governance-check.py`：文档治理检查脚本（支持 --json 输出）

## 六、经验教训

1. **先用现有工具**：仓库中已有 `doc-governance-autofix.py`，在自制修复逻辑前应先了解和复用现有工具
2. **处理自定义 schema 时要保留原有字段**：直接替换 frontmatter 会丢失原有字段（如 topic、generated_at、counts），需解析旧 frontmatter 并按需合并
3. **注意 YAML 格式**：使用 `pyyaml.safe_dump` 等库确保生成合法的 YAML，而不是手工拼接字符串
4. **bin-quota 约束**：新增 bin 脚本必须保持净增为 0，否则会触发门禁。建议复用现有脚本而不是新建
5. **runtime 约束**：`runtime/` 目录下的文件严禁提交到 git，生成时应注意路径
6. **子模块状态**：处理过程中需注意子模块的未跟踪文件，及时清理避免影响父仓库状态

## 七、后续建议

1. **完善 autofix 脚本**：将本次总结的自定义 schema 处理逻辑合并到 `doc-governance-autofix.py` 中，使其能自动处理 `resident-retro-candidate/v1` 等特殊 schema
2. **预防性治理**：在文档生成脚本（如 resident retro 生成器）中，直接生成符合治理要求的 frontmatter，避免事后修复
3. **定期巡检**：定期运行 `doc-governance-check.py`，及时发现和处理元数据不一致问题
4. **固化检查清单**：将常见的修复模式纳入日常治理 SOP

## 八、完成状态

- ✅ 文档治理检查：4638 文件，0 警告（PASS）
- ✅ 全量提炼修复模式、映射规则、处理差异
- ✅ 固化全局记忆和技能
- ✅ 产出详细的提炼与蒸馏文档（本文档）

本轮“提炼和蒸馏环节”已按既定计划完成。
