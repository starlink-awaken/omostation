---
schema_version: report/v1
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-02
last_updated: 2026-09-02
bet: BET-Y1Q4-T10-01
---

# DLP 防泄密围栏与自动脱敏沙箱（交付报告）

## 交付概览

| 项 | 结果 |
|----|------|
| 规则引擎 | 6 类敏感数据（涉密文号/密级标识/身份证/手机号/内部 IP/财务预算），<2ms 热路径零模型 |
| 识别率 | **100% 零漏报**（评测集 14 正例 + 3 对抗例，零误报）✅ |
| 判定时延 | **0.148ms**（median-of-5，长文本 5×拼接）✅ |
| 高危挂起 | quarantine + 报警文案逐字命中 done_when："检测到机密文号，需夏明星二次确认" ✅ |
| 多级脱敏 | partial（首尾保留）/ mask / redact，脱敏产物复扫零残留 ✅ |
| NER 插件 | 接口在位（uer/roberta-cluener），模型不在位快速跳过——规则层独保契约 |
| 命令面 | `cockpit dlp-guard --file/--text [--sanitize]`，exit 2 = 高危挂起 ✅ |
| 红线 | 未脱敏原文不外传；高危永不自动外发 ✅ |

## 实测样例

```
输入: 国卫办发布〔2026〕15号文件，联系人 13812345678，
      内网节点 100.99.210.78，年度预算 3500万元。
→ 4 处发现 (2 high + 2 medium) | status: pending_approval
→ ⛔ 检测到机密文号、机密财务预算，需夏明星二次确认
```

## 关键工程决策

1. **分层契约语义**：规则层独保 done_when 的 100%/2ms（regex 热路径）；
   NER 是能力增强插件非契约依赖——模型加载慢/缺失不阻塞核心闸。
2. **Python re 可选链怪癖**（新坑入档）：`万?亿元?` 三连可选回溯短路失配
   （`亿?万元?` 却能过）——单位匹配改显式 alternation
   `(?:万亿元?|亿元?|万元?)` 根治。
3. 报警类型标签中文化映射（TYPE_LABELS 单源），契约文案逐字对齐。

## Verify

- ecos venv: `python -m ecos.governance.dlp_broker --test-dlp` → 5 检查全绿 exit 0
- `make gac-local-gate` → PASS
- tests/test_dlp_guard.py 7/7 ✅
