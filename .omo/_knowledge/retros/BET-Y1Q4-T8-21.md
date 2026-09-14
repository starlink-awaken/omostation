---
schema_version: retrospective/v1
bet_id: BET-Y1Q4-T8-21
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-14
---

# BET-Y1Q4-T8-21 复盘: 决策提案闭环消费

## 交付摘要

**状态**: 代码交付完成 (3/4 done_when 已满足)
**剩余**: 存量 133 份提案批量归档 (human_gate, 需 operator 执行)

### 已交付

1. **CLI 接线** — `cockpit resident decision triage/approve/status` 已可执行
   - 修改 `resident.py` 拦截 decision 子命令，cockpit 原生处理
   - 其他 `decision` 子命令仍委派 omo

2. **扫描器修复** — `triage_status` 优先，不再混淆 doc lifecycle `status`
   - 原代码 `meta.get("status") or meta.get("triage_status")` 将 `status: archived` 误判为 triage 结果
   - 修复后 121 份提案正确显示为 unreviewed

3. **单元测试** — 17/17 通过 (scan/filter/status/triage/approve/registration)

4. **Web API** — `GET /api/decisions` 端点已就绪

### 待 operator 执行

```bash
cd projects/omo && uv run python -c "
from omo.resident.decision import batch_archive_status
result = batch_archive_status('reviewed')
print(f'归档完成: {result[\"marked\"]}/{result[\"total\"]} 份')
"
```

dry-run 结果: 133 份全部标记为 reviewed, 0 跳过。

## 架构决策

- **CLI 拦截而非新增顶层命令**: `cockpit resident decision triage` 复用现有 `resident` REMAINDER 机制，在 `cmd_resident()` 内拦截特定子命令，避免 argparse 子命令与 REMAINDER 冲突
- **triage_status 与 status 分离**: `triage_status` 是分诊结果，`status` 是文档生命周期状态，两者语义不同不可混淆
- **approve 经 omo broker 落盘**: `write_delivery_template()` 经 contract_gatekeeper 管控，不直写 .omo/

## 陷阱记录

1. **argparse REMAINDER + 子命令冲突**: `resident` 使用 `nargs=argparse.REMAINDER`，无法直接添加子命令。解法：在 `cmd_resident()` 内手动拦截
2. **doc lifecycle status ≠ triage status**: `status: archived` 是文档归档状态，`triage_status: reviewed` 是分诊结果。扫描器须区分
3. **omo submodule TLS 克隆失败**: worktree 创建时 omo 克隆因 LibreSSL TLS 错误失败，用 symlink 绕过
4. **uv venv 依赖缺失**: worktree 中 cockpit venv 缺少 kairon-observability，测试须在主仓运行

## 验证

```bash
cd projects/cockpit && uv run pytest tests/test_resident_decision_triage.py -q  # 17 passed
uv run cockpit resident decision triage --json  # 结构化输出
uv run cockpit resident decision status  # 归档进度
```
