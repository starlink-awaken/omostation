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
