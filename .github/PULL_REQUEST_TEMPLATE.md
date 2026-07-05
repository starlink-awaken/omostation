## PR Checklist (omo governance audit 自动跑)

- [ ] 跑过本地 CI: `./scripts/ci_local.sh`
- [ ] `omo governance audit` 总分 >= 95
- [ ] 0 missing deliverables (P36 治理债务永久化)
- [ ] operating-rhythm pre_release 跑过: `cockpit governance rhythm pre_release` (PR 合并前 gate, Meadows 9, ADR-0121 维度 3)
- [ ] agora 12/12 健康 (如改动 agora)
- [ ] kairon 0 ruff errors (如改动 kairon)
- [ ] deliverables 列全部为文件路径 (非描述式)

### 改动概述

<!-- 简述 PR 改了什么 -->

### 关联任务

<!-- P32 / P33 / P34 / P35 / P36 / P37-XXX-XXX -->

### 验收命令

```bash
./scripts/ci_local.sh
```
