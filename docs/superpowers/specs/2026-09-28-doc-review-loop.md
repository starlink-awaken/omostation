---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-28
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 业务第三单 — 卫健委域三份 docx 的结构化审阅支持（文档审阅环首跑）
bet_id: BET-Y2Q4-T4-05
---

# BET-Y2Q4-T4-05 — 文档审阅环首跑

## 授权链

principal 批准"业务从 documents 下提炼"并两次「继续」确认文档审阅形态。三份真实文档实勘（1,922/2,899/7,540 字，均为 principal 有权处理的卫健委域工作文档）。

## 交付物（全部落 principal Documents 域，零正文入仓）

1. **五年总结审阅意见**（`_drafts/`）：字数核对（实 1,922 / 要求 2000，余量 78）、结构映射、
   亮点提炼、与 144 号纪要新部署的衔接建议（如"区级覆盖"路径、"三医"协同监管）；
2. **审核意见复核笔记**（`_drafts/`）：对既有审核意见做第二双眼睛复核——预算算术独立复算
   （163+157=320、90.55×1.8≈163）、材料清单与汇编交叉核对、遗漏项建议；
3. **申报完整性核对清单**（`_templates/`，可复用资产）：由汇编（7,540 字申报流程+材料清单+模板）
   转化为 markdown 核对清单，供后续项目申报复用。

## 红线

- 三份审阅产物只落 principal Documents 域（`_drafts/` + `_templates/`），仓库零正文；
- 审阅意见标注"供 principal 参考采纳"，不直接改写原报送稿；
- 预算数字复核结果如实呈现（对/错/存疑），不臆断。

## 验收

1. 三份产物落位（`_drafts/` ×2 + `_templates/` ×1）；
2. 五年总结字数核对含余量结论；预算复算独立完成（非抄审核意见结论）；
3. 核对清单结构化（checkbox 化、可复用）；
4. 报告/retro 入仓零正文；principal 采纳节留槽。
