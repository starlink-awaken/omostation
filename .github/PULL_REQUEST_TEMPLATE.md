## PR Checklist (omo governance audit 自动跑)

- [ ] 跑过本地 CI: `./scripts/ci_local.sh`
- [ ] `omo governance audit` 总分 >= 95
- [ ] 0 missing deliverables (P36 治理债务永久化)
- [ ] operating-rhythm pre_release 跑过: `cockpit governance rhythm pre_release` (PR 合并前 gate, Meadows 9, ADR-0121 维度 3)
- [ ] agora 12/12 健康 (如改动 agora)
- [ ] kairon 0 ruff errors (如改动 kairon)
- [ ] deliverables 列全部为文件路径 (非描述式)

### 回归测试声明 (BET-Y2Q4-T10-02, fix 类 PR 必填)

<!-- fix 类 PR 二选一: [x] 已附回归测试 (列出测试文件/用例) 或 [x] 豁免 + 理由
     (纯文档/生成态/子模块指针类 fix 可豁免). 详见 docs/reports/test-density-baseline-2026-09-26.md -->

- [ ] 本 PR 是 fix 类, 已附回归测试: `<测试文件:用例>`
- [ ] 本 PR 是 fix 类, 声明豁免, 理由: `<一句话>`
- [ ] 本 PR 非 fix 类 (feat/chore/docs/test/ci/refactor...)

### 改动概述

<!-- 简述 PR 改了什么 -->

### 关联任务

<!-- P32 / P33 / P34 / P35 / P36 / P37-XXX-XXX -->

### 验收命令

```bash
./scripts/ci_local.sh
```
