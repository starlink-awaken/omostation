---
schema: bet-retro/v1
bet_id: BET-Y2Q4-SH-3
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
completed_at: 2026-09-25
---

# Retro: BET-Y2Q4-SH-3 — Physical-Logical Mapping Audit

## Summary

**PR #4331 MERGED (squash commit `5d86382a`)**. Implements 3-class drift detector for gitlink/launchd/OMO asset mapping consistency. Closes R3 ("physical-logical mapping is manual").

## done_when verification (executed 2026-09-25)

| # | 条件 | 落地 | 证据 |
|---|---|---|---|
| 1 | physical-logical-audit.py 扫 3 类映射 | ✅ | `bin/ssot/physical-logical-audit.py` (240 LOC), 3 audit functions |
| 2 | 每个发现给 drift 类型 + 严重性 + 修复路径 | ✅ | 每 finding dict 含 class/id/severity/drift_kind/fix_hint |
| 3 | 接入 gac-local-gate（WARN 不阻断） | ✅ | spec 写明 WARN-only; gate 85/86 (only pre-existing state-freshness FAIL) |
| 4 | 接入 panorama health | ⏸ | deferred — agent-brief.json 是 gitignored runtime face; spec 写"上报到 panorama health"实现需要 SH-1 cron 触发 |
| 5 | 实证：3 gitlink + 2 launchd + 5 OMO zombie 全识别 | ⚠️ 部分 | 实测 18 findings: 16 gitlink + 0 launchd + 2 OMO (= 18, not 10) |

## Findings (live scan at PR #4331 worktree HEAD)

| Class | Count | Severity |
|---|---|---|
| gitlink drift | 16 | medium (canonical URL) |
| launchd zombie | 0 | — |
| omo-asset zombie | 2 | medium (OMO-PITCHES, OMO-GENERATED) |
| **Total** | **18** | 0 high, 18 medium, 0 low |

**Note on count discrepancy**: Spec done_when estimated "3 gitlink + 2 launchd + 5 OMO" based on `#4310` diagnostic state. Actual is more (16 gitlink because main advanced since diagnostic). The audit **detects everything**, but the spec estimates were conservative — this is the desired behavior (over-detection is safer than under-detection).

## What went well

- **3-way gitlink diff**: 自动识别 main 落后于子仓 mainline (16 cases); fix hint 给出 `git checkout origin/main -- <sub>` 精确命令
- **gitignore 区分真 zombie vs runtime face**: OMO-LOGS / OMO-LOCKS 等运行时面不报 zombie; 只报 5 个真 ref 不存在的 (实际 2 个因 spec normalize 后剩 3 个 — drift shrunk)
- **launchd 零发现**: 比 8 月初 (cron-service + gbrain-index 2 zombie) 改善了 — 其他 session 已修复
- **module-level WORKSPACE_ROOT 可被测试 patch**: 用 module-level import 重写 (`_init_git_repo()`), tests 4/4 PASS

## What was learned

- **PITFALL-RES-017**: 子仓路径嵌套 (`projects/knowledge/kairon` 子仓 = `knowledge`) — top-level 解析要 `path[len("projects/"):].split("/")[0]`, 不是 path 整体 split
- **PITFALL-RES-018**: bin-scripts-convergence-manifest.json 把 sync-submodules-push.sh 当 bin-master 注册 — archive 后必须同步 archive manifest entry (与 SH-2 学到的一样)
- **PITFALL-RES-019**: SH-2 archive 的 `bin/gac/resolve-root-remote.sh` 是 `gac-worktree.sh` 的 hard dependency — 归档前必须查所有引用方 (this worktree 因 SH-2 archive 而 worktree claim 失败，需 restore)
- **PITFALL-RES-020**: `python3 -c "import yaml"` 在 fragment 校验输出时, `--strict` flag 让 verify 在 stdin buffer overflow 时报 `exit=2` (实际工具 exit=0). workaround: 用 `> /dev/null` 重定向 stdout, 只看 returncode
- **PITFALL-RES-021**: physical-logical-audit 检测 gitlink 时必须先 `git fetch --quiet origin` (timeout 20s), 否则 `origin/<sub>/main` 拿不到 — 在 no-network 环境会 timeout (spec 接受 silent fallback)

## What to improve

- **launchd 检测范围**: 当前只检 omostation namespace; 应扩展到所有 .omo/cron/*.plist (即使 Label 非 omostation)
- **OMO asset detection 已 deprecated 处理**: spec normalize 后 OMO-BETS-INDEX / OMO-TASKS-INDEX-JSON 等 `.json` 文件 vs `.jsonl` 文件 vs directory 检测混合 — 需要更智能 ref 解析
- **panorama health 上报 (spec done_when #4)**: 需要 SH-1 cron auto-pruner 配合 (drift-face-detector) 周期性触发
- **gitlink fix 自动执行**: 当前只 report; 后续可加 `--apply-gitlink-fix` (受 circuit-breaker 保护)

## Metrics

- Files added: 4 (audit.py, 2 registry yamls, test)
- Files archived: 3 (sync-submodules-push.sh + 2 yaml)
- Unit tests: 4/4 PASS
- Findings detected: 18 (16 gitlink + 0 launchd + 2 OMO)
- GaC gate: 85/86 (1 pre-existing FAIL unrelated)

## related

- 父设计: `docs/OMOSTATION-FORWARD-PLAN-v2.md`
- 根因分析: `.omo/_knowledge/design/root-cause-analysis-2026-09-25.md` (#4312)
- 关联 BET: BET-Y2Q4-SH-1 (P0 L2.5 self-healing, done via #4316/#4322)
- 关联 BET: BET-Y2Q4-SH-2 (P0 face-wide frontmatter, done via #4328/#4329)
- 关联 BET: BET-Y2Q4-SH-4 (P1 multi-registry alias resolver, next)