#!/bin/bash
# gac-branch-protection.sh — main branch protection 设置 (ADR-0106, P2)
#
# 多 agent 并行的平台兜底: 禁 direct push main + Require PR.
# 治本 concurrent-agent-contention (agent 绕不过平台, 被迫走 PR).
#
# 影响 (破坏性, 改全局流程):
#   - 所有 agent (含老王 + 并发) direct push main 被拒
#   - 必须走 PR (gac-worktree.sh claim → submit → merge)
#   - 配合 worktree per session = 多 agent 真并行 (各 worktree 各 PR)
#
# 策略 (过渡):
#   - Require PR (核心隔离) ✅
#   - 禁 direct push ✅
#   - Enforce admins ✅ (堵 admin 绕过, 治本 concurrent-agent-contention)
#   - Required status: phase-gate (ADR-0223 阶段门硬阻断)
#   - 0 required reviews (单人可 merge, 不阻塞)
#
# 用法:
#   gac-branch-protection.sh --check        # 查 protection 状态 (解析各项, 可读)
#   gac-branch-protection.sh --promote-gac-gate --expected-digest <sha256:...> [--yes]
#   gac-branch-protection.sh --rollback-gac-gate --expected-digest <sha256:...> [--yes]
#   gac-branch-protection.sh --remove       # 移除 (紧急回退, 交互)
#   gac-branch-protection.sh --remove --yes # 移除 (非交互)
#
# 落地计划: docs/AGENT-ISOLATION-ROLLOUT.md (Phase 3, 需 Phase 2 eCOS 迁 PR 先行)

set -e

REPO="${GAC_BRANCH_PROTECTION_REPO:-starlink-awaken/omostation}"

# 解析: 第一个位置参数 = 子命令, 其余扫描 --yes
cmd="${1:---set}"
[ $# -gt 0 ] && shift
AUTO_YES=false
# F-1 修: --yes/-y 作为首参数单独用 (无 subcommand 时走默认 --set, 见 line 20 文档)
case "$cmd" in
  --yes|-y) AUTO_YES=true; cmd="--set" ;;
esac
for arg in "$@"; do
  case "$arg" in
    --yes|-y) AUTO_YES=true ;;
  esac
done

if [ "$cmd" = "--rollback-gac-gate" ]; then
  EXPECTED_CONTEXTS="${GAC_EXPECTED_CONTEXTS:-phase-gate,bet-done-transition,gac-gate}"
elif [ "$cmd" = "--check" ]; then
  EXPECTED_CONTEXTS="${GAC_CHECK_EXPECTED_CONTEXTS:-phase-gate,bet-done-transition,gac-gate}"
else
  EXPECTED_CONTEXTS="${GAC_EXPECTED_CONTEXTS:-phase-gate,bet-done-transition}"
fi
EXPECTED_DIGEST="${GAC_EXPECTED_PROTECTION_DIGEST:-}"
for arg in "$@"; do
  case "$arg" in
    --expected-contexts=*) EXPECTED_CONTEXTS="${arg#*=}" ;;
    --expected-digest=*) EXPECTED_DIGEST="${arg#*=}" ;;
  esac
done
while [ "$#" -gt 0 ]; do
  case "$1" in
    --expected-contexts|--expected-digest)
      [ "$#" -ge 2 ] || { echo "❌ $1 requires a value" >&2; exit 2; }
      if [ "$1" = "--expected-contexts" ]; then EXPECTED_CONTEXTS="$2"; else EXPECTED_DIGEST="$2"; fi
      shift 2
      ;;
    *) shift ;;
  esac
done

# 非交互模式 (--yes) 跳过 read, 否则交互确认 (agent/CI 用 --yes)
confirm_action() {
  local prompt="$1"
  if [ "$AUTO_YES" = "true" ]; then
    echo "⚡ 非交互 (--yes): $prompt"
    return 0
  fi
  read -p "$prompt (yes/no): " confirm
  [ "$confirm" = "yes" ] || { echo "取消"; exit 0; }
}

# H1c CAS helper. The API response contains read-only URL/check fields, so the
# Python normalizer keeps only writable protection fields and hashes that
# redacted representation for the expected-before check.
cas_update_gac_gate() {
  local action="$1"
  local expected_contexts="$2"
  local expected_digest="$3"
  local snapshot payload expected_payload after_snapshot
  snapshot=$(mktemp "${TMPDIR:-/tmp}/gac-protection.XXXXXX")
  payload="${snapshot}.payload"
  expected_payload="${snapshot}.expected"
  after_snapshot="${snapshot}.after"
  trap 'rm -f "$snapshot" "$payload" "$expected_payload" "$after_snapshot"' RETURN

  gh api --include "repos/$REPO/branches/main/protection" >"$snapshot"
  local before_digest
  before_digest=$(python3 - "$snapshot" "$payload" "$expected_payload" "$expected_contexts" "$expected_digest" "$action" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

snapshot_path = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
expected_path = Path(sys.argv[3])
expected_contexts = [item for item in sys.argv[4].split(",") if item]
expected_digest = sys.argv[5]
action = sys.argv[6]


def read_response(path: Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    marker = text.find("\n{")
    if marker < 0:
        raise SystemExit("CAS_JSON_BODY_MISSING")
    body = text[marker + 1 :]
    data, _ = json.JSONDecoder().raw_decode(body.lstrip())
    if not isinstance(data, dict):
        raise SystemExit("CAS_JSON_BODY_INVALID")
    return data


def enabled(value: object) -> bool:
    return bool(value.get("enabled")) if isinstance(value, dict) else bool(value)


def normalized(data: dict) -> dict:
    reviews = data.get("required_pull_request_reviews")
    if isinstance(reviews, dict):
        review_payload = {
            key: reviews[key]
            for key in (
                "required_approving_review_count",
                "dismiss_stale_reviews",
                "require_code_owner_reviews",
                "require_last_push_approval",
            )
            if key in reviews
        }
    else:
        review_payload = None

    status = data.get("required_status_checks")
    if isinstance(status, dict):
        status_payload = {
            "strict": bool(status.get("strict")),
            "contexts": list(status.get("contexts") or []),
        }
    else:
        status_payload = None

    restrictions = data.get("restrictions")
    if isinstance(restrictions, dict):
        restrictions_payload = {
            key: list(restrictions.get(key) or [])
            for key in ("users", "teams", "apps")
            if key in restrictions
        }
    else:
        restrictions_payload = None

    result = {
        "required_pull_request_reviews": review_payload,
        "enforce_admins": enabled(data.get("enforce_admins")),
        "required_status_checks": status_payload,
        "restrictions": restrictions_payload,
    }
    for key in (
        "required_linear_history",
        "allow_force_pushes",
        "allow_deletions",
        "block_creations",
        "required_conversation_resolution",
        "lock_branch",
        "allow_fork_syncing",
    ):
        if key in data:
            result[key] = enabled(data[key])
    return result


def digest(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


live = read_response(snapshot_path)
current = normalized(live)
status = current.get("required_status_checks") or {}
actual_contexts = list(status.get("contexts") or [])
if sorted(actual_contexts) != sorted(expected_contexts):
    raise SystemExit(
        "CAS_EXPECTED_CONTEXTS_MISMATCH: "
        + ",".join(actual_contexts)
        + " != "
        + ",".join(expected_contexts)
    )
actual_digest = digest(current)
if not expected_digest:
    raise SystemExit("CAS_EXPECTED_DIGEST_REQUIRED: before=" + actual_digest)
if actual_digest != expected_digest:
    raise SystemExit(f"CAS_EXPECTED_DIGEST_MISMATCH: before={actual_digest} expected={expected_digest}")

desired = json.loads(json.dumps(current))
desired_status = desired.get("required_status_checks") or {"strict": False, "contexts": []}
contexts = list(desired_status.get("contexts") or [])
if action == "promote":
    if "gac-gate" not in contexts:
        contexts.append("gac-gate")
elif action == "rollback":
    contexts = [item for item in contexts if item != "gac-gate"]
else:
    raise SystemExit("CAS_ACTION_INVALID")
desired_status["contexts"] = contexts
desired["required_status_checks"] = desired_status
api_payload = {
    "strict": bool(desired_status.get("strict")),
    "contexts": contexts,
}
payload_path.write_text(json.dumps(api_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
expected_path.write_text(json.dumps(desired, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(actual_digest)
PY
)
  echo "H1c expected-before digest: $before_digest"
  echo "H1c desired context set: ${expected_contexts},gac-gate (action=$action)"
  # GitHub disallows conditional headers on this unsafe endpoint. PATCHing the
  # dedicated status-check subresource minimizes the write set; the expected
  # full-payload digest and exact-after GET provide optimistic CAS semantics.
  gh api "repos/$REPO/branches/main/protection/required_status_checks" -X PATCH --input "$payload" >/dev/null
  gh api --include "repos/$REPO/branches/main/protection" >"$after_snapshot"
  python3 - "$after_snapshot" "$expected_payload" <<'PY'
import json
import re
import sys
from pathlib import Path

response = Path(sys.argv[1]).read_text(encoding="utf-8")
expected = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
marker = response.find("\n{")
if marker < 0:
    raise SystemExit("CAS_AFTER_JSON_BODY_MISSING")
actual, _ = json.JSONDecoder().raw_decode(response[marker + 1 :].lstrip())


def enabled(value: object) -> bool:
    return bool(value.get("enabled")) if isinstance(value, dict) else bool(value)


def normalize(data: dict) -> dict:
    reviews = data.get("required_pull_request_reviews")
    review_payload = None
    if isinstance(reviews, dict):
        review_payload = {k: reviews[k] for k in ("required_approving_review_count", "dismiss_stale_reviews", "require_code_owner_reviews", "require_last_push_approval") if k in reviews}
    status = data.get("required_status_checks")
    status_payload = None if not isinstance(status, dict) else {"strict": bool(status.get("strict")), "contexts": list(status.get("contexts") or [])}
    restrictions = data.get("restrictions")
    restrictions_payload = None if not isinstance(restrictions, dict) else {k: list(restrictions.get(k) or []) for k in ("users", "teams", "apps") if k in restrictions}
    result = {"required_pull_request_reviews": review_payload, "enforce_admins": enabled(data.get("enforce_admins")), "required_status_checks": status_payload, "restrictions": restrictions_payload}
    for key in ("required_linear_history", "allow_force_pushes", "allow_deletions", "block_creations", "required_conversation_resolution", "lock_branch", "allow_fork_syncing"):
        if key in data:
            result[key] = enabled(data[key])
    return result


if normalize(actual) != expected:
    raise SystemExit("CAS_AFTER_PAYLOAD_MISMATCH")
print("CAS exact-after verification: PASS")
PY
}

case "$cmd" in
  --promote-gac-gate)
    confirm_action "确认仅追加 gac-gate 到 main required contexts?"
    cas_update_gac_gate "promote" "$EXPECTED_CONTEXTS" "$EXPECTED_DIGEST"
    ;;

  --rollback-gac-gate)
    confirm_action "确认仅移除 gac-gate required context?"
    cas_update_gac_gate "rollback" "$EXPECTED_CONTEXTS" "$EXPECTED_DIGEST"
    ;;

  --check)
    echo "=== $REPO main branch protection 状态 ==="
    set +e
    resp=$(gh api "repos/$REPO/branches/main/protection" 2>/dev/null)
    api_rc=$?
    set -e
    if [ "$api_rc" -ne 0 ]; then
      echo "❌ protection unreadable (API rc=$api_rc)"
      exit 2
    fi
    python3 - "$EXPECTED_CONTEXTS" "$resp" <<'PY'
import json
import sys

expected = sorted(item for item in sys.argv[1].split(",") if item)
try:
    data = json.loads(sys.argv[2])
    actual = sorted((data.get("required_status_checks") or {}).get("contexts") or [])
except (TypeError, ValueError, AttributeError):
    print("❌ protection unreadable (invalid JSON)")
    raise SystemExit(2)
print("  Required status chks:  " + (",".join(actual) or "none"))
print("  Expected status chks:  " + (",".join(expected) or "none"))
if actual != expected:
    print("❌ protection drift")
    raise SystemExit(1)
print("✅ protection aligned")
PY
    ;;

  --remove)
    echo "❌ refusing legacy full protection deletion; use --rollback-gac-gate CAS subcommand" >&2
    exit 2
    ;;

  --help|-h)
    sed -n '2,30p' "$0"
    ;;

  *)
    echo "❌ refusing legacy full-payload branch-protection write; use explicit CAS subcommand" >&2
    echo "   promote: $0 --promote-gac-gate --expected-digest sha256:<64-hex> --yes" >&2
    echo "   check:   $0 --check" >&2
    exit 2
    ;;
esac
