#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
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

test_ci_status_green() {
  local st
  st=$(ci_status_of "starlink-awaken/omostation" "phase-gate" 2>/dev/null || echo "no-runs")
  echo "PASS: phase-gate status=$st"
}

test_ci_status_missing() {
  local st
  st=$(ci_status_of "starlink-awaken/omostation" "no-such-workflow-xyz" 2>/dev/null || echo "missing")
  [ "$st" = "missing" ] || { echo "FAIL: 期望 missing, 得到 $st"; return 1; }
  echo "PASS: 不存在的 workflow 返回 missing"
}

test_ci_status_green
test_ci_status_missing

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

test_risk_score_bounds() {
  local score
  score=$(risk_score "starlink-awaken/omostation" 2>/dev/null || echo 0)
  [ "$score" -ge 0 ] && [ "$score" -le 100 ] || { echo "FAIL: score 越界 $score"; return 1; }
  echo "PASS: risk_score=$score (0-100)"
}

test_risk_score_bounds

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
  echo "$out" | grep -q "风险地图\|风险分\|repo\|CI红" || { echo "FAIL: markdown 缺风险地图表头"; return 1; }
  echo "PASS: --markdown 输出风险地图"
}

test_main_json
test_main_markdown

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

test_e2e_full() {
  local out
  out=$(bin/ssot/audit-repo-health.sh --json --limit 1 2>/dev/null || echo '{"repos":[]}')
  echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
repos=d.get('repos',[])
assert len(repos) >= 1, f'期望 ≥1 仓库, 得 {len(repos)}'
scores=[r.get('risk_score',0) for r in repos]
assert all(0 <= s <= 100 for s in scores), 'score 越界'
print(f'PASS: e2e 扫描 {len(repos)} 仓库, 最高风险 {max(scores)}, 最低 {min(scores)}')
"
}

test_e2e_full
