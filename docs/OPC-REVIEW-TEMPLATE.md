# OPC Review Template

> Status: 2026-06-12 (P7-H5 closeout)
> Source-of-truth: 派工红线 "每个 agent 提交时必须附" 8 字段

## 1. 用途

所有 OPC 阶段 closeout / 子门验收 / 跨 phase PR / 跨仓改动 review, 必须用本模板
填写 8 字段, 不允许字段缺失 (缺失则 verdict 强制 `request changes`)。

## 2. 模板 (copy & fill)

```markdown
## OPC Review

### 1. Phase/Subgate
- Phase: OPC-P{X} (例如 OPC-P6)
- Subgate: {ID} (例如 P6-G3)
- Plan: `.omo/tasks/planned/OPC-P{X}-{NAME}.yaml`
- Date: {YYYY-MM-DD}

### 2. Objective
{1-2 句: 这个 subgate 的核心目标, 引用 plan yaml 的 description 段}

### 3. Files changed
- {file1 path:line} — {一句话描述}
- {file2 path:line} — {一句话描述}
- (子仓独立 commit 引用: 子仓 {name} @ {commit-sha})

### 4. Commands run
```bash
{所有执行的命令, 每条 1 行, 含 exit code 期望}
```
```text
{实际输出摘要, 含 exit code 数值}
```

### 5. Runtime evidence
- 单元测试: `pytest {path} -q` → `{N} passed in {T}s`
- 真实数据样本: `{path to sample}`
- 落盘证据: `{path to .omo/_delivery/.../...}`

### 6. Doc/task writeback
- [ ] docs/{file} 已更新 (Status / Gate / 信号)
- [ ] .omo/tasks/planned/OPC-P{X}.yaml sub-gate status=passed + closeout
- [ ] .omo/tasks/registry/done/{ID}/evidence-package.md 落地
- [ ] omo/tests/test_opc_phase_governance_alignment.py 三面一致测试

### 7. Open risks
- (红线 6 项 / forbidden_claims / expansion creep 等)
- (已知限制, 留 R57+ 范围)

### 8. Requested verdict
- [ ] LGTM (approve & merge)
- [ ] Request changes (必须说明变更点)
- [ ] Needs more evidence (必须说明缺什么)

Reviewer: ____  Date: ____
```

## 3. 红线 (request changes 强制触发)

- 缺任何 1 个字段 → request changes
- "测试通过" == "gate passed" 暗示 → request changes
- 未跑 ≥1 周就声明 drift detector passed → request changes
- 候选 task < 3 (G2) 或 audit trail < 3 仓 (G4) → request changes
- self-evolution task 出现在 active/ → request changes

## 4. 示例

参考: `.omo/tasks/registry/done/OPC-P6-G4/evidence-package.md`
       `docs/OPC-MASTER-EXECUTION-PLAYBOOK.md` §Phase status
