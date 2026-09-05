---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-08-18
type: ssot
---
# PITFALL-002: 双平面纯净度破坏 (Documents 脚本与依赖污染)

- **条目编号**: `PITFALL-002`
- **严重等级**: `CRITICAL`
- **关联架构**: ADR-0191 Workspace x Documents 双平面架构
- **首次踩坑**: 2026-08-16

---

## 1. 踩坑现象与根因

### 现象
Agent 在处理业务公文、表格分析或企微通知时，习惯性地在 `~/Documents/@工作文档/` 目录下就地创建 `.py` 脚本、`.sh` 辅助脚本，或者初始化虚拟环境 `.venv` / `node_modules`。这导致业务内容目录与工程代码严重混杂，破坏双平面边界。

### 根因
Agent 缺乏物理空间隔离认知，习惯在“就近路径”编写执行脚本。

---

## 2. 规避配方 (Safe Pattern Recipe)

严格遵循 **Workspace 存放代码与工具，Documents 存放事实与产物** 的铁律：

```bash
# ❌ 错误示范 (Anti-Pattern)
~/Documents/@工作文档/卫健委/parse_excel.py
~/Documents/@工作文档/国转中心/.venv/

# ✅ 正确范式 (Safe Recipe)
# 脚本统一沉淀在 Workspace 项目中：
~/workspace/projects/runtime/scripts/domain/parse_weijian_excel.py
# Documents 中仅保留纯粹的 Markdown / YAML / DOCX / PDF 数据：
~/Documents/@工作文档/卫健委/2026-08-基层卫生调研报告.docx
```
