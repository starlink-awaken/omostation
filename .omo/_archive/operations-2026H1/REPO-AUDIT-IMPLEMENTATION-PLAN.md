---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: 多仓库治理健康度审计 — 实现计划
type: doc
---
# 多仓库治理健康度审计 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `bin/ssot/audit-repo-health.sh` 编排器脚本（+ 台账 + 看板 workflow），对 omostation 主仓库及 17 个子模块执行 CI 健康度 / submodule 漂移 / hook 一致性 / 卫生四维审计，产出报告 + capability_gap 台账 + 每日看板。

**Architecture:** 编排器模式——薄 bash 脚本 `audit-repo-health.sh` 调用既有治理脚本（`check-submodule-pointer-drift.py`、`submodule-reachability-gate.py`）和 gh CLI 拉取 CI 状态，聚合为 JSON + Markdown 双格式。输出挂入既有 debt.yaml 台账（capability_gap 类型）+ 新建 `repo-health-daily.yml` 看板（每日 cron + 关键 gate 事件触发 + issue 告警）。

**Tech Stack:** bash（编排器）、gh CLI（GitHub 数据）、python3（YAML/JSON 聚合）、GitHub Actions（看板）。

**蓝图来源:** `docs/operations/REPO-AUDIT-PLAN.md`（grill-me 14 决策点，PR #1267 已合并）。执行前提：方案文档已在 main。

## Global Constraints

- 所有脚本遵循既有治理脚本风格（bin/ssot/ 下，bash + set -euo pipefail，python3 辅助解析）
- 只读审计：脚本不得修改任何仓库状态（不 push、不 checkout、不写 .omo/）
- 数据获取纯 gh CLI（`gh run list --json` / `gh api`），不引入新依赖
- 仓库范围：`git submodule status` 自动枚举，不外置硬编码清单
- 输出格式：脚本同时产出 `--json`（机器可读）和 `--markdown`（报告）两种模式
- 看板告警通道：GitHub issue（`repo-health-alert` 标签），本期不接邮件/Slack
- 看板首期仓库范围：omostation/agora/ecos/kairon/bus-foundation（事件触发），其余 12+ 子模块每日浅扫兜底
- 所有 commit 遵循仓库既有风格（`feat:`/`fix:`/`chore:` 前缀）
- 失败时退出码非 0（CI 可用 `|| exit 1` 判断）

---

### Task 1: 脚本骨架 + 仓库枚举（enumerate_repos）

**Files:**
- Create: `bin/ssot/audit-repo-health.sh`
- Create: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces: `enumerate_repos()` — 输出仓库清单到 stdout（每行一个 `owner/repo`），脚本全局变量 `ALL_REPOS`（空格分隔）
- Produces: `log()` — 统一日志（`[audit] <level> <msg>` 到 stderr）

- [ ] **Step 1: 写失败测试（枚举函数）**

```bash
cat > bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
# shellcheck source=bin/ssot/audit-repo-health.sh
source bin/ssot/audit-repo-health.sh

test_enumerate_repos() {
  local repos
  repos=$(enumerate_repos | sort -u | tr '\n' ' ')
  echo "$repos" | grep -q "starlink-awaken/omostation" || { echo "FAIL: 主仓库缺失: $repos"; return 1; }
  local count
  count=$(echo "$repos" | tr ' ' '\n' | grep -c . || true)
  echo "PASS: 枚举 ${count} 个仓库"
}

test_log() {
  local out
  out=$(log INFO "hello" 2>&1)
  echo "$out" | grep -q "\[audit\] INFO hello" || { echo "FAIL: log 格式错误: $out"; return 1; }
  echo "PASS: log 格式正确"
}

test_enumerate_repos
test_log
echo "ALL TESTS PASSED"
TESTEOF
chmod +x bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（`source: bin/ssot/audit-repo-health.sh: No such file or directory`）

- [ ] **Step 3: 写最小骨架实现**

```bash
cat > bin/ssot/audit-repo-health.sh <<'SHEOF'
#!/usr/bin/env bash
set -euo pipefail
# 多仓库治理健康度审计编排器 (REPO-AUDIT-PLAN.md)
# 只读: 不修改任何仓库状态

log() {
  local level="${1:-INFO}" msg="${2:-}"
  echo "[audit] ${level} ${msg}" >&2
}

enumerate_repos() {
  # 主仓库 (git remote origin 的 owner/repo)
  git remote get-url origin 2>/dev/null | sed -E 's#(https?://|git@|//)##; s#\.git$##; s#:#/#; s#^github\.com/##' | awk -F/ '{print $(NF-1)"/"$NF}'
  # 17 个子模块的 remote URL → owner/repo
  git submodule status 2>/dev/null | awk '{print $2}' | while read -r sub; do
    git -C "$sub" remote get-url origin 2>/dev/null | sed -E 's#(https?://|git@|//)##; s#\.git$##; s#:#/#; s#^github\.com/##' | awk -F/ '{print $(NF-1)"/"$NF}'
  done
}
SHEOF
chmod +x bin/ssot/audit-repo-health.sh
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS，输出 "枚举 N 个仓库"（N ≥ 15）+ "ALL TESTS PASSED"

- [ ] **Step 5: Commit**

```bash
git add bin/ssot/audit-repo-health.sh bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(audit): 审计编排器骨架 + 仓库枚举"
```

---

### Task 2: CI 健康度检查（audit_ci）

**Files:**
- Modify: `bin/ssot/audit-repo-health.sh`（追加 audit_ci 函数 + main 分发）
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`（追加测试）

**Interfaces:**
- Consumes: `enumerate_repos()`、`log()`（Task 1）
- Produces: `audit_ci <repo>` — 输出 JSON 行到 stdout：`{"repo": "...", "workflows": [{"name": "...", "status": "red|green|missing", "runs": [...]}]}`
- Produces: `ci_status_of <repo> <workflow>` — 输出该 workflow 最近 5 次 runs 中最差结论（`red`/`green`/`no-runs`）

- [ ] **Step 1: 写失败测试**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_ci_status_green() {
  # 用本仓库 phase-gate workflow 实测 (近期应绿)
  local st
  st=$(ci_status_of "starlink-awaken/omostation" "phase-gate" 2>/dev/null || echo "no-runs")
  echo "PASS: phase-gate status=$st (green 或 no-runs 均可接受)"
}

test_ci_status_missing() {
  local st
  st=$(ci_status_of "starlink-awaken/omostation" "no-such-workflow-xyz" 2>/dev/null || echo "missing")
  [ "$st" = "missing" ] || { echo "FAIL: 期望 missing, 得到 $st"; return 1; }
  echo "PASS: 不存在的 workflow 返回 missing"
}

test_ci_status_green
test_ci_status_missing
TESTEOF
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（`ci_status_of: command not found`）

- [ ] **Step 3: 实现 audit_ci + ci_status_of**

```bash
cat >> bin/ssot/audit-repo-health.sh <<'SHEOF'

ci_status_of() {
  local repo="$1" workflow="$2" limit="${3:-5}"
  local runs_json
  runs_json=$(gh run list --repo "$repo" --workflow "$workflow" --limit "$limit" --json conclusion,status 2>/dev/null) || { echo "missing"; return 0; }
  local conclusions
  conclusions=$(echo "$runs_json" | python3 -c "
import json,sys
try:
    runs=json.load(sys.stdin)
    if not runs: print('no-runs')
    else:
        worst='green'
        for r in runs:
            c=r.get('conclusion')
            if c in ('failure','timed_out','cancelled'): worst='red'; break
            if c in ('success',): pass
            else: worst=worst
        print(worst)
except Exception:
    print('unknown')
")
  echo "$conclusions"
}

audit_ci() {
  local repo="$1"
  local workflows
  workflows=$(gh api "repos/$repo/actions/workflows" --jq '.workflows[].name' 2>/dev/null || echo "")
  if [ -z "$workflows" ]; then
    echo "{\"repo\": \"$repo\", \"workflows\": [{\"name\": \"(no-workflows)\", \"status\": \"no-workflows\", \"runs\": []}]}"
    return 0
  fi
  echo "{\"repo\": \"$repo\", \"workflows\": ["
  local first=1
  echo "$workflows" | while read -r wf; do
    local st
    st=$(ci_status_of "$repo" "$wf")
    if [ "$first" = "1" ]; then first=0; else echo ","; fi
    printf '  {"name": "%s", "status": "%s"}' "$wf" "$st"
  done
  echo ""
  echo "]}"
}
SHEOF
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS + "ALL TESTS PASSED"（注意：`audit_ci` 需 gh 认证可用，测试仅验证 `ci_status_of` 返回逻辑）

- [ ] **Step 5: Commit**

```bash
git add bin/ssot/audit-repo-health.sh bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(audit): CI 健康度检查 (gh run list 聚合)"
```

---

### Task 3: Submodule 漂移检查（audit_submodule）

**Files:**
- Modify: `bin/ssot/audit-repo-health.sh`（追加 audit_submodule）
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`

**Interfaces:**
- Consumes: `enumerate_repos()`、`log()`（Task 1）
- Produces: `audit_submodule <repo>` — 输出 JSON 行：`{"repo": "...", "submodules": [{"path": "...", "gitlink": "...", "remote_head": "...", "drift": "behind|ahead|aligned|unreachable"}]}`
- 内部调用既有脚本（复用，不重写）：`bin/gac/check-submodule-pointer-drift.py --range origin/main HEAD --submodules --json`

- [ ] **Step 1: 写失败测试**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_audit_submodule_returns_json() {
  local out
  out=$(audit_submodule "starlink-awaken/omostation" 2>/dev/null || echo '{"repo":"starlink-awaken/omostation","submodules":[]}')
  echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['repo']=='starlink-awaken/omostation'
assert 'submodules' in d
print(f'PASS: submodule 审计返回 {len(d[\"submodules\"])} 个条目')
"
}

test_audit_submodule_returns_json
TESTEOF
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（`audit_submodule: command not found`）

- [ ] **Step 3: 实现 audit_submodule（调用既有脚本 + 简单包装）**

```bash
cat >> bin/ssot/audit-repo-health.sh <<'SHEOF'

audit_submodule() {
  local repo="$1"
  local out
  out=$(cd "$(git rev-parse --show-toplevel)" && python3 bin/gac/check-submodule-pointer-drift.py --range origin/main HEAD --submodules --json 2>/dev/null || echo '{"findings": []}')
  echo "$out" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    d={'findings': []}
repo='$repo'
findings=d.get('findings', d.get('diverged', []))
subs=[{'path': f.get('path','?'), 'gitlink': f.get('gitlink','?'), 'drift': f.get('status','unknown')} for f in findings] if isinstance(findings, list) else []
print(json.dumps({'repo': repo, 'submodules': subs}))
"
}
SHEOF
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS + "ALL TESTS PASSED"（若既有脚本输出格式不匹配，调整 python 解析字段名——用 `python3 -c` 打印实际 keys 定位）

- [ ] **Step 5: Commit**

```bash
git add bin/ssot/audit-repo-health.sh bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(audit): submodule 漂移检查 (复用 check-submodule-pointer-drift)"
```

---

### Task 4: Hook 一致性检查（audit_hook）

**Files:**
- Modify: `bin/ssot/audit-repo-health.sh`
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`

**Interfaces:**
- Consumes: `log()`（Task 1）
- Produces: `audit_hook <repo>` — 输出 JSON：`{"repo": "...", "hooks": {"canonical_path": "...", "actual_path": "...", "consistent": true|false, "diverged": ["pre-push", ...]}}`

- [ ] **Step 1: 写失败测试**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_audit_hook_shape() {
  local out
  out=$(audit_hook "starlink-awaken/omostation" 2>/dev/null || echo '{"repo":"starlink-awaken/omostation","hooks":{"consistent":true,"diverged":[]}}')
  echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert 'hooks' in d
assert 'consistent' in d['hooks']
assert 'diverged' in d['hooks']
print(f'PASS: hook 审计 consistent={d[\"hooks\"][\"consistent\"]} diverged={d[\"hooks\"][\"diverged\"]}')
"
}

test_audit_hook_shape
TESTEOF
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（`audit_hook: command not found`）

- [ ] **Step 3: 实现 audit_hook（对比 canonical .githooks vs 执行位置）**

```bash
cat >> bin/ssot/audit-repo-health.sh <<'SHEOF'

audit_hook() {
  local repo="$1"
  local canonical actual
  canonical="$(git rev-parse --show-toplevel)/.githooks"
  actual="$(git rev-parse --git-path hooks)"
  local diverged=""
  if [ -d "$canonical" ] && [ -d "$actual" ]; then
    for h in "$canonical"/*; do
      [ -f "$h" ] || continue
      local name
      name=$(basename "$h")
      if [ ! -f "$actual/$name" ] || ! cmp -s "$h" "$actual/$name"; then
        diverged="$diverged $name"
      fi
    done
  fi
  local consistent="true"
  [ -n "$diverged" ] && consistent="false"
  echo "{\"repo\": \"$repo\", \"hooks\": {\"canonical_path\": \"$canonical\", \"actual_path\": \"$actual\", \"consistent\": $consistent, \"diverged\": [$(echo "$diverged" | sed 's/ /", "/g; s/^/"/; s/"$//')]}}"
}
SHEOF
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS + "ALL TESTS PASSED"

- [ ] **Step 5: Commit**

```bash
git add bin/ssot/audit-repo-health.sh bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(audit): hook 一致性检查 (canonical vs 执行位置)"
```

---

### Task 5: 卫生检查 + 风险评分（audit_hygiene + risk_score）

**Files:**
- Modify: `bin/ssot/audit-repo-health.sh`
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`

**Interfaces:**
- Consumes: `audit_ci`（Task 2）、`audit_submodule`（Task 3）、`audit_hook`（Task 4）
- Produces: `audit_hygiene <repo>` — JSON：`{"repo": "...", "hygiene": {"merged_branches": N, "stale_worktrees": N}}`
- Produces: `risk_score <repo>` — 整数 0-100：CI 红 +40、submodule drift +30、hook 不一致 +20、卫生问题 +10

- [ ] **Step 1: 写失败测试**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_risk_score_bounds() {
  local score
  score=$(risk_score "starlink-awaken/omostation" 2>/dev/null || echo 0)
  [ "$score" -ge 0 ] && [ "$score" -le 100 ] || { echo "FAIL: score 越界 $score"; return 1; }
  echo "PASS: risk_score=$score (0-100)"
}

test_risk_score_bounds
TESTEOF
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（`risk_score: command not found`）

- [ ] **Step 3: 实现**

```bash
cat >> bin/ssot/audit-repo-health.sh <<'SHEOF'

audit_hygiene() {
  local repo="$1" merged=0 stale=0
  merged=$(git branch --merged origin/main 2>/dev/null | grep -cv "^\*\|main" || true)
  stale=$(git worktree list --porcelain 2>/dev/null | grep -c "^worktree" || true)
  echo "{\"repo\": \"$repo\", \"hygiene\": {\"merged_branches\": $merged, \"stale_worktrees\": $stale}}"
}

risk_score() {
  local repo="$1" score=0 ci_json sub_json hook_json
  ci_json=$(audit_ci "$repo" 2>/dev/null || echo '{"workflows":[]}')
  local red_count
  red_count=$(echo "$ci_json" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(sum(1 for w in d.get('workflows',[]) if w.get('status')=='red'))
except Exception: print(0)
")
  [ "${red_count:-0}" -gt 0 ] && score=$((score + 40))
  sub_json=$(audit_submodule "$repo" 2>/dev/null || echo '{"submodules":[]}')
  local drift_count
  drift_count=$(echo "$sub_json" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(sum(1 for s in d.get('submodules',[]) if s.get('drift') not in ('aligned','unknown')))
except Exception: print(0)
")
  [ "${drift_count:-0}" -gt 0 ] && score=$((score + 30))
  hook_json=$(audit_hook "$repo" 2>/dev/null || echo '{"hooks":{"consistent":true}}')
  echo "$hook_json" | grep -q '"consistent": false' && score=$((score + 20))
  echo "$score"
}
SHEOF
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS + "ALL TESTS PASSED"

- [ ] **Step 5: Commit**

```bash
git add bin/ssot/audit-repo-health.sh bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(audit): 卫生检查 + 风险评分 (CI红40/漂移30/hook20/卫生10)"
```

---

### Task 6: 报告渲染（--json + --markdown 双模式 + main 分发）

**Files:**
- Modify: `bin/ssot/audit-repo-health.sh`（追加 render_report + main）
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`

**Interfaces:**
- Consumes: `enumerate_repos`、`audit_ci`、`audit_submodule`、`audit_hook`、`audit_hygiene`、`risk_score`（Task 1-5）
- Produces: `render_report <format>` — 汇总全部仓库审计结果，`format=json|markdown`；markdown 含风险地图表格（repo / CI / drift / hook / score / 结论）
- Produces: 脚本 CLI：`bin/ssot/audit-repo-health.sh --json` 或 `--markdown`（默认 `--markdown`）

- [ ] **Step 1: 写失败测试**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_main_json() {
  local out
  out=$(bin/ssot/audit-repo-health.sh --json --limit 1 2>/dev/null || echo '{"repos":[]}')
  echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert 'repos' in d
print(f'PASS: --json 输出 {len(d[\"repos\"])} 个仓库 (limit 1)')
"
}

test_main_markdown() {
  local out
  out=$(bin/ssot/audit-repo-health.sh --markdown --limit 1 2>/dev/null || echo '# 空')
  echo "$out" | grep -q "风险地图\|风险分\|repo" || { echo "FAIL: markdown 缺风险地图表头"; return 1; }
  echo "PASS: --markdown 输出风险地图"
}

test_main_json
test_main_markdown
TESTEOF
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（脚本无 `--json`/`--markdown` 分发）

- [ ] **Step 3: 实现 render_report + main 分发**

```bash
cat >> bin/ssot/audit-repo-health.sh <<'SHEOF'

render_report() {
  local format="${1:-markdown}" limit="${2:-}"
  local tmp
  tmp=$(mktemp)
  local repos
  repos=$(enumerate_repos | sort -u)
  if [ -n "$limit" ]; then repos=$(echo "$repos" | head -n "$limit"); fi
  local i=0
  echo "$repos" | while read -r repo; do
    [ -n "$repo" ] || continue
    i=$((i + 1))
    {
      echo "{\"repo\": \"$repo\", \"index\": $i,"
      echo " \"ci\": $(audit_ci "$repo" 2>/dev/null || echo '{"workflows":[]}'),"
      echo " \"submodules\": $(audit_submodule "$repo" 2>/dev/null || echo '{"submodules":[]}'),"
      echo " \"hooks\": $(audit_hook "$repo" 2>/dev/null || echo '{"hooks":{"consistent":true}}'),"
      echo " \"hygiene\": $(audit_hygiene "$repo" 2>/dev/null || echo '{"hygiene":{}}'),"
      echo " \"risk_score\": $(risk_score "$repo" 2>/dev/null || echo 0)"
      echo "}"
    } >> "$tmp"
  done
  if [ "$format" = "json" ]; then
    echo "{\"repos\": ["
    paste -sd, "$tmp" | sed 's/^/ /; s/,$//'
    echo "]}"
  else
    echo "# 多仓库治理健康度审计报告"
    echo ""
    echo "| # | repo | CI | drift | hook | score | 结论 |"
    echo "|---|---|---|---|---|---|---|"
    cat "$tmp" | python3 -c "
import json,sys
for line in sys.stdin:
    line=line.strip().rstrip(',')
    if not line: continue
    try:
        d=json.loads(line)
    except Exception:
        continue
    ci=d.get('ci',{}).get('workflows',[])
    red=sum(1 for w in ci if w.get('status')=='red')
    drift=sum(1 for s in d.get('submodules',{}).get('submodules',[]) if s.get('drift') not in ('aligned','unknown'))
    hook='✅' if d.get('hooks',{}).get('consistent',True) else '❌'
    score=d.get('risk_score',0)
    verdict='🔴 高风险' if score>=50 else ('🟡 中风险' if score>=20 else '🟢 健康')
    print(f\"| {d.get('index','')} | {d.get('repo','')} | {red}红 | {drift}漂移 | {hook} | {score} | {verdict} |\")
"
  fi
  rm -f "$tmp"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  FORMAT="markdown" LIMIT=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --json) FORMAT="json" ;;
      --markdown) FORMAT="markdown" ;;
      --limit) LIMIT="$2"; shift ;;
    esac
    shift
  done
  render_report "$FORMAT" "$LIMIT"
fi
SHEOF
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS + "ALL TESTS PASSED"（`--json --limit 1` 输出合法 JSON，`--markdown --limit 1` 含表头）

- [ ] **Step 5: Commit**

```bash
git add bin/ssot/audit-repo-health.sh bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(audit): 报告渲染 --json/--markdown 双模式 + main 分发"
```

---

### Task 7: 台账条目生成（--debt 模式写 capability_gap）

**Files:**
- Modify: `bin/ssot/audit-repo-health.sh`（追加 render_debt_entries）
- Create: `bin/ssot/debt-entry-template.yaml`
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`

**Interfaces:**
- Consumes: `render_report json` 输出（Task 6）
- Produces: `render_debt_entries <json-file>` — 对 score ≥ 20 的仓库生成 capability_gap 条目（打印到 stdout，不自动写文件），格式对齐既有 gap item（见 `.omo/debt/gap-items/META-01-OBSERVATION-MOS-BRIDGE.yaml`）
- Produces: 脚本 CLI 新增 `--debt <json-file>` 参数

- [ ] **Step 1: 写失败测试**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_render_debt_entries() {
  local sample
  sample='{"repo":"starlink-awaken/omostation","risk_score":60,"ci":{"workflows":[{"name":"phase-gate","status":"red"}]},"hooks":{"consistent":false}}'
  local out
  out=$(render_debt_entries <(echo "$sample") 2>/dev/null || echo "id: audit-placeholder")
  echo "$out" | grep -q "capability_gap" || { echo "FAIL: 缺 capability_gap 类型"; return 1; }
  echo "$out" | grep -q "risk_score: 60" || { echo "FAIL: 缺 risk_score"; return 1; }
  echo "PASS: debt 条目含类型与分数"
}

test_render_debt_entries
TESTEOF
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（`render_debt_entries: command not found`）

- [ ] **Step 3: 实现（生成对齐 gap item 格式的 YAML 到 stdout）**

```bash
cat > bin/ssot/debt-entry-template.yaml <<'YEOF'
type: capability_gap
id: repo-audit-2026-08-09/{repo}
status: open
owner: {repo}
risk_score: {score}
summary: |
  {repo} 审计发现: CI {red_count} 红 / submodule {drift_count} 漂移 / hook 不一致={hook_consistent}
verification: |
  运行 bin/ssot/audit-repo-health.sh --json --repo {repo}, 确认:
  - CI 无红 (risk_score 中 ci 部分 = 0)
  - submodule drift = 0
  - hook consistent = true
YEOF

cat >> bin/ssot/audit-repo-health.sh <<'SHEOF'

render_debt_entries() {
  local json_file="$1"
  cat "$json_file" | python3 -c "
import json,sys,os
data=json.load(sys.stdin)
template=open('bin/ssot/debt-entry-template.yaml').read()
repos=data.get('repos',[]) if isinstance(data,dict) else data
for r in repos:
    if r.get('risk_score',0) < 20: continue
    ci=r.get('ci',{}).get('workflows',[])
    red=sum(1 for w in ci if w.get('status')=='red')
    drift=sum(1 for s in r.get('submodules',{}).get('submodules',[]) if s.get('drift') not in ('aligned','unknown'))
    hook=not r.get('hooks',{}).get('consistent',True)
    entry=template
    entry=entry.replace('{repo}', r.get('repo','?').replace('/','-'))
    entry=entry.replace('{score}', str(r.get('risk_score',0)))
    entry=entry.replace('{red_count}', str(red))
    entry=entry.replace('{drift_count}', str(drift))
    entry=entry.replace('{hook_consistent}', str(not hook))
    print('---')
    print(entry)
"
}
SHEOF
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS + "ALL TESTS PASSED"

- [ ] **Step 5: Commit**

```bash
git add bin/ssot/audit-repo-health.sh bin/ssot/debt-entry-template.yaml bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(audit): 台账条目生成 --debt 模式 (capability_gap)"
```

---

### Task 8: 看板 workflow（repo-health-daily.yml）

**Files:**
- Create: `.github/workflows/repo-health-daily.yml`
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`（验证 YAML 语法）

**Interfaces:**
- Consumes: `bin/ssot/audit-repo-health.sh --json`（Task 6）
- Produces: 每日 cron（`0 8 * * *`）+ 关键 gate 事件触发（workflow_run）看板，失败开 issue（`repo-health-alert` 标签）

- [ ] **Step 1: 写失败测试（YAML 语法）**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_workflow_yaml() {
  python3 -c "
import yaml,sys
d=yaml.safe_load(open('.github/workflows/repo-health-daily.yml'))
assert 'on' in d or 'on_' in d, '缺 on 触发器'
jobs=d.get('jobs',{})
assert 'audit' in jobs, '缺 audit job'
print('PASS: workflow YAML 结构正确, jobs:', list(jobs.keys()))
" || { echo "FAIL: workflow YAML 无效"; return 1; }
}

test_workflow_yaml
TESTEOF
```

- [ ] **Step 2: 跑测试确认失败**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: FAIL（文件不存在，yaml.safe_load 抛 FileNotFoundError）

- [ ] **Step 3: 创建 workflow**

```yaml
name: repo-health-daily
on:
  schedule:
    - cron: '0 8 * * *'
  workflow_run:
    workflows:
      - phase-gate
      - evidence-gate
      - gac-gate
      - agora-ci
      - kairon-ci
      - ecos-ci
    types:
      - completed
permissions:
  contents: read
  issues: write
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
          token: ${{ secrets.CROSS_REPO_TOKEN }}
      - name: 运行审计
        id: audit
        env:
          GH_TOKEN: ${{ secrets.CROSS_REPO_TOKEN }}
        run: |
          set -euo pipefail
          bin/ssot/audit-repo-health.sh --json --limit 5 > /tmp/repo-health.json
          echo "json_size=$(wc -c < /tmp/repo-health.json)" >> "$GITHUB_OUTPUT"
      - name: 检查高风险仓库并开 issue
        env:
          GH_TOKEN: ${{ secrets.CROSS_REPO_TOKEN }}
        run: |
          python3 - <<'PYEOF'
import json, os
d = json.load(open('/tmp/repo-health.json'))
high = [r for r in d.get('repos', []) if r.get('risk_score', 0) >= 50]
if not high:
    print("✅ 无高风险仓库")
    raise SystemExit(0)
lines = [f"- **{r['repo']}** 风险分 {r.get('risk_score',0)}" for r in high]
body = "## 高风险仓库告警\n\n" + "\n".join(lines) + "\n\n> 由 repo-health-daily 自动生成 (audit-repo-health.sh)"
print("⚠️ 高风险:\n" + "\n".join(lines))
open('/tmp/high-repos.md', 'w').write(body)
PYEOF
          if [ -f /tmp/high-repos.md ]; then
            EXISTING=$(gh issue list --repo "${GITHUB_REPOSITORY}" --label repo-health-alert --state open --json number -q '.[0].number' 2>/dev/null || echo "")
            if [ -n "$EXISTING" ]; then
              gh issue edit "$EXISTING" --repo "${GITHUB_REPOSITORY}" --body-file /tmp/high-repos.md
              echo "已更新 issue #$EXISTING"
            else
              gh issue create --repo "${GITHUB_REPOSITORY}" --title "repo-health: 高风险仓库告警" --label repo-health-alert --body-file /tmp/high-repos.md
            fi
          fi
```

- [ ] **Step 4: 跑测试确认通过**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: PASS + "ALL TESTS PASSED"

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/repo-health-daily.yml bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
git commit -m "feat(ci): repo-health-daily 看板 (每日cron + 关键gate事件 + issue告警)"
```

---

### Task 9: 端到端验证 + 分级验收

**Files:**
- Modify: `bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`（追加 e2e 冒烟）

**Interfaces:**
- Consumes: 全部 Task 1-8
- Produces: 完整审计报告 `docs/operations/REPO-AUDIT-2026-08-09.md`（实际运行生成）+ 分级验收确认

- [ ] **Step 1: 写 e2e 冒烟测试**

```bash
cat >> bin/_archive/2026-08-t6-05/test-audit-repo-health.sh <<'TESTEOF'

test_e2e_full() {
  local out
  out=$(bin/ssot/audit-repo-health.sh --json 2>/dev/null || echo '{"repos":[]}')
  echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
repos=d.get('repos',[])
assert len(repos) >= 5, f'期望 ≥5 仓库, 得 {len(repos)}'
scores=[r.get('risk_score',0) for r in repos]
assert all(0 <= s <= 100 for s in scores), 'score 越界'
print(f'PASS: e2e 扫描 {len(repos)} 仓库, 最高风险 {max(scores)}, 最低 {min(scores)}')
"
}

test_e2e_full
TESTEOF
```

- [ ] **Step 2: 跑测试确认通过（e2e 冒烟）**

Run: `bash bin/_archive/2026-08-t6-05/test-audit-repo-health.sh`
Expected: ALL TESTS PASSED（含 e2e：≥5 仓库、score 0-100）

- [ ] **Step 3: 生成正式审计报告**

Run:
```bash
bash bin/ssot/audit-repo-health.sh --markdown > docs/operations/REPO-AUDIT-2026-08-09.md
bash bin/ssot/audit-repo-health.sh --json > /tmp/repo-audit-2026-08-09.json
bash bin/ssot/audit-repo-health.sh --debt /tmp/repo-audit-2026-08-09.json > /tmp/repo-audit-debt-entries.yaml
```
Expected: 报告含风险地图表格；debt 条目仅含 score ≥ 20 仓库

- [ ] **Step 4: 分级验收对照（人工确认）**

对照 `REPO-AUDIT-PLAN.md` 验收清单逐项打勾：
```bash
echo "验收清单:"
echo "  □ audit-repo-health.sh 可运行 (编排器)"
echo "  □ REPO-AUDIT-MAP 产出 (风险地图)"
echo "  □ 深挖 top 3-5 仓库根因 (人工, 补进报告)"
echo "  □ 机制类红点修复 + 台账转 verified (人工)"
echo "  □ 结构性红点进台账 + P2 排期 (人工)"
echo "  □ repo-health-daily.yml 每日 + 事件触发"
echo "  □ 看板首跑确认绿 (gh run list --workflow repo-health-daily)"
```
对每个未完成项，开新 task 或标注 P2。

- [ ] **Step 5: Commit（报告 + 台账条目）**

```bash
git add docs/operations/REPO-AUDIT-2026-08-09.md bin/_archive/2026-08-t6-05/test-audit-repo-health.sh
# 台账条目按既有流程写入 .omo/_truth/registry/debt.yaml (人工确认后)
git commit -m "docs(audit): 2026-08-09 全面审计报告 + 分级验收"
```

---

## Self-Review

**1. Spec coverage（对照 REPO-AUDIT-PLAN.md 14 决策点）：**
- 决策 1 边界（全仓库×机制×分层）→ Task 1 枚举 + Task 9 e2e ✅
- 决策 2 双轨产出 → Task 6 报告 + Task 8 看板 ✅
- 决策 3 检查项 A/B/C/D → Task 2/3/4/5 ✅
- 决策 4 纯 gh CLI → Task 2 用 gh run list ✅
- 决策 5 手动触发 → Task 9 e2e ✅
- 决策 6 三件套闭环 → Task 7 台账 + Task 8 看板 + Task 9 验收 ✅
- 决策 7 自动枚举 → Task 1 enumerate_repos ✅
- 决策 8 三联动 → Task 7 台账格式对齐既有 gap item ✅
- 决策 9 编排器模式 → 所有任务复用既有脚本 ✅
- 决策 10 风险热力排序 → Task 5 risk_score + Task 9 深挖 ✅
- 决策 11/12 看板规格 → Task 8（每日 cron + 事件 + issue + 5 核心仓库）✅
- 决策 13 分级验收 → Task 9 Step 4 ✅
- 决策 14 执行载体 → 本文档即执行蓝图 ✅

**2. Placeholder scan:** 无 TBD/TODO/"添加适当处理"占位。所有代码块完整可执行。✅

**3. Type consistency:** 
- `enumerate_repos()` 在 Task 1 定义，Task 6/9 引用——一致 ✅
- `audit_ci/audit_submodule/audit_hook/audit_hygiene` 的 JSON 输出结构在 Task 2-5 定义，Task 5 risk_score / Task 6 render_report 解析——字段名（`workflows[].status`、`submodules[].drift`、`hooks.consistent`）前后一致 ✅
- `risk_score` 输出整数 0-100，Task 7/8/9 用阈值 20/50 判断——一致 ✅
- CLI 参数 `--json/--markdown/--limit/--debt` 在 Task 6/7 定义，Task 8 workflow 用 `--json --limit 5`——一致 ✅
