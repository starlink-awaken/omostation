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
