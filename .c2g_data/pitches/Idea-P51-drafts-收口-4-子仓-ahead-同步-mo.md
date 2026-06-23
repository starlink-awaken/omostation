# P51 drafts 收口 + 4 子仓 ahead 同步 + mof-drift 收口

> **Upstream**: P50-GBR-TODO (mof-version v0.0.38) / OMO 100 A+ 持续
> **Appetite:** 1 day
> **Vector:** V2 (c2g brainstorm 转化)
> **Type:** Feature + 治理收口

## 背景与上下文

P50 (commit f21b7910 + 978d4b91) 完成后审计：

- **PLANNED 目录清零** (历史首次, P49 收口)
- **2 drafts 残留** (P15 历史, status=draft):
  - P15-DRAFT-LEDGER-FIRST
  - P15-DRAFT-USER-VALUE-LIVE-DEMO
- **4 子仓 ahead** (本会话未推送):
  - ecos 2 commits (P44 R0 DEBT-GBRAIN-OPERATIONS-TS 收口, workflow CLI 4 commit)
  - gbrain 15 commits (P44 R0 operations.ts 拆分 + P50 R0 调研)
  - agora 1 commit (P44 R0 接口细化)
  - aetherforge 5 commits (P44 R0 gateway 合并)
- **mof-drift 仍 3 LOW**:
  - gbrain 53 TODOs (子仓债, P50 R0 决策 4 类)
  - gbrain TODOs 5 类分类
  - gbrain TODOs Top-5 文件分布
- **mof-version v0.0.38**

## 目标

### P51 R1 (今天, 0.5h) — 立项 + drafts cascade
- **G1**: c2g bet → omo broker → P51-DRAFTS-CLEANUP PLANNED task
- **G2**: 2 drafts cascade done (P15-DRAFT-LEDGER-FIRST + P15-DRAFT-USER-VALUE-LIVE-DEMO)
- **G3**: drafts 目录清零 (历史首次)

### P51 R2 (今天, 0.5h) — 4 子仓 ahead 同步
- **G4**: 4 子仓 (ecos/gbrain/agora/aetherforge) ahead 实际状态 verify
- **G5**: bin/sync-submodules-push.sh 实跑 (按 P44 R0 模式: 1 子仓 1 commit)
- **G6**: 根仓 bump gitlink (主仓不批量 push, 但可本地 commit gitlink)

### P51 R3 (今天, 0.5h) — 收口
- **G7**: P51-DRAFTS-CLEANUP → done
- **G8**: mof-version v0.0.38 → v0.0.39
- **G9**: 收口报告入 .omo/_knowledge/audits/
- **G10**: governance 100 A+ 持续
- **G11**: mof-drift 仍 3 LOW (gbrain 子仓债, 等子仓自身 review)

## 技术要求

- **零代码改动**: 不动子仓任何代码
- **drafts 推进**: 沿用 P49 cascade 模式 (planned→active→done)
- **子仓同步**: 沿用 P43 submodule_state_decoupling 原则 (主仓不批量 push 子仓)
- **mof-drift 收口**: 仍 3 LOW (子仓债), 不假装 0

## 验收标准

1. **G1** P51-DRAFTS-CLEANUP PLANNED task 创建
2. **G2** 2 drafts done
3. **G3** drafts 目录清零
4. **G4** 4 子仓 ahead 状态 verify (子仓各自 git status)
5. **G5** sync-submodules-push.sh 实跑 (--dry-run 验证 + 实跑 commit)
6. **G6** 根仓 gitlink 更新 (P52+ 推)
7. **G7-G9** task done + mof-version v0.0.39 + 收口报告
8. **G10-G11** governance 100 A+ + mof-drift 3 LOW 持续

## 风险

| 风险 | 缓解 |
|------|------|
| 子仓 push 触发 CI 悬空 | sync-submodules-push.sh 已设计 (P44 R0 防悬空) |
| 4 子仓 23 commits 一起推 | 按子仓逐个推, 失败即停 |
| mof-drift 仍 3 LOW 算不算"收口" | 接受: gbrain 子仓债 根仓无权改 |

## 关联

- P50-GBR-TODO: ADR-0050 gbrain 4 类决策
- P49-REG-CLEANUP: PLANNED 清零
- P48-GBR-AHEAD: 17 项目 lint
- P44 R0: 4 子仓 workflow 收口 (DEBT-GBRAIN-OPERATIONS-TS)
- P43 submodule_state_decoupling: 治理原则

## NoGos (YAGNI)

- ❌ 不实施 gbrain 19 unknown TODOs (子仓工作)
- ❌ 不删任何 drafts (cascade done 不是删)
- ❌ 不动子仓任何代码
- ❌ 不重命名子仓指针 (P52+ 推)
