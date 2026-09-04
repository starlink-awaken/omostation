---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# 会话发现项方案 (2026-08-08)

> 覆盖 6 项发现, 按价值排序。每项含现状/方案/落地步骤/验证。
> 前 3 项高价值优先落地, 后 3 项中低价值。

## 一、并发安全治理 (高价值, 治本)

### 现状
共享 checkout 被并发 agent 污染的 3 次复发:
- remote 污染 (origin 被指到 agora/kairon) ×3
- 并发 agent 覆盖修复 (state-goals-enforce 改回旧版)
- 并发 merge 冲突未解决就提交 (SUBMODULE_DRIFT 冲突标记)

### 方案
1. **主仓操作全迁移 worktree**: 每任务独立 worktree + 独立分支, 共享 checkout 只读
2. **remote 校验 hook**: pre-push 前验证 origin 指向 omostation (防 remote 污染)
3. **冲突标记检测**: pre-commit 检测 .omo 数据文件含 <<<<<<< 则阻断 (防未解决冲突提交)

### 落地
- pre-push 加 remote 校验 + 冲突标记扫描 (bin/ssot/git-hygiene-check.py)
- 文档强调"共享 checkout 只读"规范

### 验证
- 模拟 origin 错误 → pre-push 阻断
- 模拟冲突标记 → pre-commit 阻断

## 二、派生文档完整性校验 (高价值, 防 CI 红)

### 现状
post-commit-sync-check 自动生成派生文档, 但本地子模块不全时生成残缺
(cli_commands=0 / bos_services=0), 残缺可能被提交污染 main.

### 方案
`post-commit-sync-check.py` 生成后**校验完整性**:
- cli_commands > 0 AND bos_services > 100 才算有效
- 残缺 → 跳过提交提示 (不污染), 标记"需 CI 完整环境"

### 落地
- sync-check 脚本加 `_validate_generation` 完整性校验

### 验证
- 本地不全 (残缺) → 提示跳过
- 完整 → 正常提交

## 三、gate-roi 规则级数据源 (中价值, 减法数据驱动)

### 现状
T6-01 减法卡在"缺规则级违规数据" (governance-history.jsonl 是 gate 级).

### 方案
governance-history.jsonl 的 checks 条目增加 `rule_id` 字段:
- 各 checker 运行后写规则级违规 (CR-XXX 级)
- gate-roi 支持按 rule_id 聚合 → 减法数据驱动

### 落地
- governance-evolution.py 或 checker 运行时带 rule_id 记录

### 验证
- governance-history 新条目含 rule_id
- gate-roi 可输出规则级建议

## 四、BET 台账自动回写 (中价值)

### 现状
BET done 状态手动维护 → 记忆/台账脱节 (实际 23 done, 记忆 4).

### 方案
bet-execution closeout 后自动标 done:
- closeout workflow 加 `bet-ledger.py complete {bet_id}` 步

### 落地
- bet-execution.yaml closeout 阶段加 complete 步

### 验证
- closeout 后台账 status=done

## 五、记忆与 git 状态同步 (低价值)

### 现状
MEMORY.md 的"65/4 done"过期 (实际 23 done).

### 方案
记忆标注"验证时点"或从 bet-ledger 读取真实状态.

### 落地
- MEMORY.md 相关条目加时间戳/指向台账

## 六、方案文档落地状态标注 (低价值)

### 现状
5 份 agora 方案文档仍是"规划"状态, 未标注 P0-P5 已完成.

### 方案
方案文档加"落地状态"段 (已完成步骤).

### 落地
- docs/plans/2026-08-07-agora-*.md 补落地状态

## 优先级
| 项 | 价值 | 复杂度 | 优先级 |
|----|------|--------|--------|
| 一 并发安全 | 高 (治本) | 中 | P0 |
| 二 派生完整性 | 高 (防 CI 红) | 低 | P0 |
| 三 规则级数据 | 中 | 中 | P1 |
| 四 台账回写 | 中 | 低 | P1 |
| 五 记忆同步 | 低 | 低 | P2 |
| 六 文档标注 | 低 | 低 | P2 |

## Review 结论 (Plan agent, 已采纳)

| 项 | 结论 | 修正 |
|----|------|------|
| 一 并发安全 | ⚠️ ①与 D2/D3/D5 重复 | 不新造轮, 引用既有 T1-00; 落地 ②remote 校验(覆盖 root+gbrain/cockpit/agora) + ③冲突标记 pre-commit |
| 二 派生完整性 | ✅ + 发现 generated_at=1970 bug | 校验 3 键 (mcp_servers/tools/bos_services) 全>0 + 修生成器写真实时间戳 |
| 三 规则级数据 | ⚠️ gate-roi 已归档, 最模糊 | 新建独立 rule-violations.jsonl, 不污染 checks 语义 |
| 四 台账回写 | ❌ bet-ledger 只读契约 | 给 bet-ledger.py 加带 guard 的 complete 子命令 (retro 通过后置 done) |
| 五 记忆同步 | ✅ | 指向台账 SSOT 而非时间戳 |
| 六 文档标注 | ✅ | 低风险, P2 |

## 修订后优先级
| 项 | 优先级 |
|----|--------|
| 二 派生完整性 (+ epoch bug) | P0 |
| 一 ②③ guard (remote 校验 + 冲突标记) | P0 |
| 四 台账 complete 子命令 | P1 |
| 三 rule-violations.jsonl | P1 |
| 五 记忆指向台账 | P2 |
| 六 文档标注 | P2 |
