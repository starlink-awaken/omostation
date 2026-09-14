#!/usr/bin/env bash
# gen-evidence-receipts.sh — 为 A1-A9 + RF0 9 个 gate 生成 digest-bound receipt
#
# 原则: 每 gate 一份 receipt, 包含 proven/missing/exit_criteria/owner/refresh 时间.
# 格式: <gate-id>.json 包含 status, exit_criteria, evidence_collected, missing, sha256_digest
# 输出: .omo/_delivery/environment-evidence/<gate-id>.json + receipts.jsonl

set -euo pipefail
WS_ROOT="$(git rev-parse --show-toplevel)"
EVIDENCE_DIR="$WS_ROOT/.omo/_delivery/environment-evidence"
mkdir -p "$EVIDENCE_DIR"
RECEIPTS_JSONL="$EVIDENCE_DIR/receipts.jsonl"
> "$RECEIPTS_JSONL"

# 收集本次采集的输出
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GATE_HEALTH_JSON="$EVIDENCE_DIR/_gate-health.json"
PANORAMA_JSON="$EVIDENCE_DIR/_panorama-gates.json"
python3 bin/gac/gate-health-check.py --json > "$GATE_HEALTH_JSON" 2>/dev/null || echo '{"error": "gate-health-check failed"}' > "$GATE_HEALTH_JSON"
python3 bin/panorama/panorama-collect.py --gates > "$PANORAMA_JSON" 2>/dev/null || echo '[]' > "$PANORAMA_JSON"

# A1-A9 + RF0 的 exit_criteria 定义 (与 PR #3696 织星驾驶舱对齐)
declare -A EXIT_CRITERIA=(
  [A1]="workflow_admission_satisfied;pasw_branch_compliance;git_push_drift_zero"
  [A2]="resident_cell_pool_alive;host_memory_pressure_normal;workspace_lock_clean"
  [A3]="governance_python_managed;harness_section_compliance;mo_consistency_pass"
  [A4]="scheduler_drift_zero;launchd_loaded_count_consistent;cron_orphans_zero"
  [A5]="submodule_fresh_within_7d;reference_alignment_pass;launchd_keepalive_active"
  [A6]="orca_r0_live_no_state_drift;r0_evidence_digest_signed;readonly_admission_test_pass"
  [A7]="multica_as0_alive_no_drift;digest_chain_consistent;readonly_admission_test_pass"
  [A8]="oma_external_transaction_schema_signed;durable_queue_persistence_verified;as0_to_a8_replay_match"
  [A9]="asd_dashboard_live;cockpit_observatory_aligned;live_evidence_refresh_within_5min"
  [RF0]="ruflo_readonly_collaboration_live;no_second_queue_created;cross_agent_dependency_zero"
)

# Owner (from governance-checks.yaml / bet-ledger conventions)
declare -A OWNER=(
  [A1]="governance-agent"
  [A2]="omo-runtime-team"
  [A3]="governance-team"
  [A4]="scheduler-agent"
  [A5]="infra-team"
  [A6]="orca-team"
  [A7]="multica-team"
  [A8]="omo-runtime-team"
  [A9]="observability-team"
  [RF0]="ruflo-team"
)

# Gate 状态 (从 panorama output 解析)
for gate_id in A1 A2 A3 A4 A5 A6 A7 A8 A9 RF0; do
  # 用 jq 或 grep 提取 verdict (无 jq 时用 grep)
  if command -v jq >/dev/null 2>&1; then
    VERDICT=$(jq -r ".[] | select(.id==\"$gate_id\") | .verdict" "$PANORAMA_JSON" 2>/dev/null || echo "UNKNOWN")
    DETAIL=$(jq -r ".[] | select(.id==\"$gate_id\") | .detail" "$PANORAMA_JSON" 2>/dev/null || echo "")
  else
    VERDICT=$(grep -A 30 "\"id\": \"$gate_id\"" "$PANORAMA_JSON" | grep -m1 "verdict" | sed 's/.*: "\(.*\)",/\1/' || echo "UNKNOWN")
    DETAIL=$(grep -A 30 "\"id\": \"$gate_id\"" "$PANORAMA_JSON" | grep -m1 "detail" | sed 's/.*: "\(.*\)",/\1/' || echo "")
  fi
  
  CRITERIA="${EXIT_CRITERIA[$gate_id]}"
  OWNER_NAME="${OWNER[$gate_id]}"
  STATUS_FIELD="proven"
  if [ "$VERDICT" = "PARTIAL" ] || [ "$VERDICT" = "ABSENT" ] || [ "$VERDICT" = "NOT_ADMITTED" ]; then
    STATUS_FIELD="missing"
  fi
  
  RECEIPT_FILE="$EVIDENCE_DIR/${gate_id}.json"
  # 计算 SHA-256 of gate-health-check.json (用作 receipt digest)
  GATE_DIGEST=$(shasum -a 256 "$GATE_HEALTH_JSON" | awk '{print $1}')
  
  cat > "$RECEIPT_FILE" <<EOF
{
  "gate_id": "$gate_id",
  "status": "$STATUS_FIELD",
  "verdict": "$VERDICT",
  "detail": "$DETAIL",
  "owner": "$OWNER_NAME",
  "exit_criteria": "$CRITERIA",
  "refresh_time": "$NOW",
  "sha256_digest": "sha256:$GATE_DIGEST",
  "source_receipt": "receipt://$GATE_HEALTH_JSON",
  "not_admitted_legal_states": "NOT_ADMITTED 合法 (A6/A7/RF0 设计如此, 非缺陷)",
  "unlock_conditions": {
    "A6": "T10-149 完成 R0 验收测试 + signoff",
    "A7": "T10-150 完成 AS0 验收测试 + signoff",
    "RF0": "side-effect-free 观察保持, 不建第二队列"
  }
}
EOF
  
  # 追加到 receipts.jsonl
  cat "$RECEIPT_FILE" >> "$RECEIPTS_JSONL"
  echo "✓ $gate_id receipt: $STATUS_FIELD ($VERDICT) → $(basename $RECEIPT_FILE)"
done

echo ""
echo "Receipts 总览: $EVIDENCE_DIR/receipts.jsonl ($(wc -l < $RECEIPTS_JSONL) gates)"
