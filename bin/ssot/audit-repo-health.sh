#!/usr/bin/env bash
set -euo pipefail
# 多仓库治理健康度审计编排器 (REPO-AUDIT-IMPLEMENTATION-PLAN.md)
# 只读: 不修改任何仓库状态

log() {
  local level="${1:-INFO}" msg="${2:-}"
  echo "[audit] ${level} ${msg}" >&2
}

enumerate_repos() {
  # 主仓库
  git remote get-url origin 2>/dev/null | sed -E 's#(https?://|git@|//)##; s#\.git$##; s#:#/#; s#^github\.com/##' | awk -F/ '{print $(NF-1)"/"$NF}'
  # 子模块
  git submodule status 2>/dev/null | awk '{print $2}' | while read -r sub; do
    git -C "$sub" remote get-url origin 2>/dev/null | sed -E 's#(https?://|git@|//)##; s#\.git$##; s#:#/#; s#^github\.com/##' | awk -F/ '{print $(NF-1)"/"$NF}'
  done
}

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
    echo "{\"repo\": \"$repo\", \"workflows\": [{\"name\": \"(no-workflows)\", \"status\": \"no-workflows\"}]}"
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

audit_hook() {
  local repo="$1"
  local canonical actual
  canonical="$(git rev-parse --show-toplevel)/.githooks"
  actual="$(git rev-parse --git-path hooks)"
  local diverged="["
  local first=1
  if [ -d "$canonical" ] && [ -d "$actual" ]; then
    for h in "$canonical"/*; do
      [ -f "$h" ] || continue
      local name
      name=$(basename "$h")
      if [ ! -f "$actual/$name" ] || ! cmp -s "$h" "$actual/$name"; then
        [ "$first" = "1" ] && first=0 || diverged="$diverged, "
        diverged="$diverged\"$name\""
      fi
    done
  fi
  diverged="$diverged]"
  local consistent="true"
  [ "$diverged" != "[]" ] && consistent="false"
  echo "{\"repo\": \"$repo\", \"hooks\": {\"canonical_path\": \"$canonical\", \"actual_path\": \"$actual\", \"consistent\": $consistent, \"diverged\": $diverged}}"
}

audit_hygiene() {
  local repo="$1" merged=0 stale=0
  merged=$(git branch --merged origin/main 2>/dev/null | grep -cv "^\*\|main" || true)
  stale=$(git worktree list --porcelain 2>/dev/null | grep -c "^worktree" || true)
  echo "{\"repo\": \"$repo\", \"hygiene\": {\"merged_branches\": $merged, \"stale_worktrees\": $stale}}"
}

audit_mof() {
  local repo="$1"
  if [ "$repo" = "starlink-awaken/omostation" ]; then
    local mof_res
    mof_res=$(uv run python3 bin/mof/gen-mof-artifacts.py --json 2>/dev/null || echo '{"drifts": 1, "findings": []}')
    echo "{\"repo\": \"$repo\", \"mof\": $mof_res}"
  else
    echo "{\"repo\": \"$repo\", \"mof\": {\"drifts\": 0, \"findings\": []}}"
  fi
}

risk_score() {
  local repo="$1" score=0 ci_json sub_json hook_json mof_json
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
  
  mof_json=$(audit_mof "$repo" 2>/dev/null || echo '{"mof":{"drifts":0}}')
  local mof_drift
  mof_drift=$(echo "$mof_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('mof',{}).get('drifts',0))" 2>/dev/null || echo 0)
  [ "${mof_drift:-0}" -gt 0 ] && score=$((score + 25))

  echo "$score"
}

render_report() {
  local format="${1:-markdown}" limit="${2:-}"
  local repos
  repos=$(enumerate_repos | sort -u)
  if [ -n "$limit" ]; then repos=$(echo "$repos" | head -n "$limit"); fi
  local tmp
  tmp=$(mktemp)
  echo "$repos" | while read -r repo; do
    [ -n "$repo" ] || continue
    local ci sub hook hyg score mof
    ci=$(audit_ci "$repo" 2>/dev/null || echo '{"workflows":[]}')
    sub=$(audit_submodule "$repo" 2>/dev/null || echo '{"submodules":[]}')
    hook=$(audit_hook "$repo" 2>/dev/null || echo '{"hooks":{"consistent":true}}')
    hyg=$(audit_hygiene "$repo" 2>/dev/null || echo '{"hygiene":{}}')
    score=$(risk_score "$repo" 2>/dev/null || echo 0)
    mof=$(audit_mof "$repo" 2>/dev/null || echo '{"mof":{"drifts":0}}')
    local mof_obj
    mof_obj=$(echo "$mof" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('mof',{})))" 2>/dev/null || echo '{"drifts":0}')
    echo "{\"repo\":\"$repo\",\"ci\":$ci,\"submodules\":$sub,\"hooks\":$hook,\"hygiene\":$hyg,\"mof\":$mof_obj,\"risk_score\":$score}" >> "$tmp"
  done
  if [ "$format" = "json" ]; then
    local items
    items=$(paste -sd, "$tmp" 2>/dev/null || cat "$tmp" | tr '\n' ',')
    echo "{\"repos\":[${items}]}"
  else
    echo "# 多仓库治理健康度审计报告"
    echo ""
    echo "| repo | CI红 | drift | hook | MOF漂移 | score | 结论 |"
    echo "|---|---|---|---|---|---|---|"
    cat "$tmp" | python3 -c "
import json,sys
for line in sys.stdin:
    line=line.strip().rstrip(',')
    if not line: continue
    try: d=json.loads(line)
    except Exception: continue
    ci=d.get('ci',{}).get('workflows',[])
    red=sum(1 for w in ci if w.get('status')=='red')
    drift=sum(1 for s in d.get('submodules',{}).get('submodules',[]) if s.get('drift') not in ('aligned','unknown'))
    hook='✅' if d.get('hooks',{}).get('consistent',True) else '❌'
    mof=d.get('mof',{}).get('drifts',0)
    score=d.get('risk_score',0)
    verdict='🔴 高风险' if score>=50 else ('🟡 中风险' if score>=20 else '🟢 健康')
    print(f\"| {d.get('repo','')} | {red}红 | {drift}漂移 | {hook} | {mof} | {score} | {verdict} |\")
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

render_debt_entries() {
  local json_file="$1"
  python3 -c "
import json,sys,os
data=json.load(open('$json_file'))
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
