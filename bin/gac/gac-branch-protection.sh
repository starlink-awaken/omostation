#!/bin/bash
# gac-branch-protection.sh — guarded required-context updates for main.
#
# The writer only touches the required_status_checks subresource. It reads
# the full protection payload before and immediately before the PATCH, then
# reads it once more to prove the requested result and all protected fields.

set -euo pipefail

REPO="${GAC_BRANCH_PROTECTION_REPO:-starlink-awaken/omostation}"
PROTECTION_ENDPOINT="repos/$REPO/branches/main/protection"
STATUS_ENDPOINT="$PROTECTION_ENDPOINT/required_status_checks"
DEFAULT_CHECK_CONTEXTS="${GAC_CHECK_EXPECTED_CONTEXTS:-phase-gate,bet-done-transition,gac-gate}"

usage() {
  cat <<EOF
Usage:
  $0 --check [--expected-contexts CONTEXTS]
  $0 --add-required-context gac-gate --expected-contexts CONTEXTS --receipt PATH [--yes]
  $0 --remove-required-context gac-gate --expected-contexts CONTEXTS --receipt PATH [--yes]
EOF
}

die_usage() {
  echo "❌ $1" >&2
  usage >&2
  exit 2
}

cmd="${1:-}"
[ "$cmd" ] || die_usage "a command is required"
shift

mode=""
target=""
expected_contexts=""
expected_contexts_set=false
receipt=""
receipt_set=false
auto_yes=false
yes_set=false

case "$cmd" in
  --check)
    mode="check"
    expected_contexts="$DEFAULT_CHECK_CONTEXTS"
    ;;
  --add-required-context)
    [ "$#" -gt 0 ] || die_usage "--add-required-context requires a context"
    mode="add"
    target="$1"
    shift
    ;;
  --remove-required-context)
    [ "$#" -gt 0 ] || die_usage "--remove-required-context requires a context"
    mode="remove"
    target="$1"
    shift
    ;;
  --help|-h)
    usage
    exit 0
    ;;
  *)
    die_usage "unsupported command: $cmd"
    ;;
esac

while [ "$#" -gt 0 ]; do
  case "$1" in
    --expected-contexts)
      [ "$expected_contexts_set" = false ] || die_usage "--expected-contexts may be supplied only once"
      [ "$#" -gt 1 ] || die_usage "--expected-contexts requires a value"
      expected_contexts="$2"
      expected_contexts_set=true
      shift 2
      ;;
    --expected-contexts=*)
      [ "$expected_contexts_set" = false ] || die_usage "--expected-contexts may be supplied only once"
      expected_contexts="${1#*=}"
      expected_contexts_set=true
      shift
      ;;
    --receipt)
      [ "$mode" != check ] || die_usage "--receipt is only valid for context updates"
      [ "$receipt_set" = false ] || die_usage "--receipt may be supplied only once"
      [ "$#" -gt 1 ] || die_usage "--receipt requires a path"
      receipt="$2"
      receipt_set=true
      shift 2
      ;;
    --receipt=*)
      [ "$mode" != check ] || die_usage "--receipt is only valid for context updates"
      [ "$receipt_set" = false ] || die_usage "--receipt may be supplied only once"
      receipt="${1#*=}"
      receipt_set=true
      shift
      ;;
    --yes|-y)
      [ "$mode" != check ] || die_usage "--yes is not valid for --check"
      [ "$yes_set" = false ] || die_usage "--yes may be supplied only once"
      auto_yes=true
      yes_set=true
      shift
      ;;
    *)
      die_usage "unsupported option: $1"
      ;;
  esac
done

[ "$expected_contexts" ] || die_usage "--expected-contexts requires a non-empty value"

if [ "$mode" != check ]; then
  [ "$target" = "gac-gate" ] || die_usage "only gac-gate may be changed"
  [ "$receipt_set" = true ] || die_usage "context updates require --receipt"
  [ "$receipt" ] || die_usage "--receipt requires a non-empty path"
  receipt_parent="$(dirname "$receipt")"
  [ -d "$receipt_parent" ] || die_usage "receipt parent does not exist: $receipt_parent"
  [ ! -e "$receipt" ] || die_usage "receipt already exists: $receipt"
fi

confirm_action() {
  local prompt="$1"
  if [ "$auto_yes" = true ]; then
    echo "⚡ non-interactive (--yes): $prompt"
    return 0
  fi
  if ! [ -t 0 ]; then
    echo "❌ interactive confirmation required; pass --yes" >&2
    return 1
  fi
  local confirm=""
  read -r -p "$prompt (yes/no): " confirm
  if [ "$confirm" != yes ]; then
    echo "cancelled" >&2
    return 1
  fi
}

get_protection() {
  local destination="$1"
  local api_rc
  if gh api --include "$PROTECTION_ENDPOINT" >"$destination"; then
    return 0
  else
    api_rc=$?
    echo "❌ protection unreadable (API rc=$api_rc)" >&2
    return 2
  fi
}

# Keep parsing and normalization in one implementation so GET A, GET B, and
# GET C use exactly the same full-protection contract. Update runs in this
# process so the reservation descriptors remain open for the whole operation.
python_tool() {
  python3 - "$@" <<'PY'
from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class OperationError(Exception):
    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


class PathIdentityError(OperationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 1)


def fail(message: str, code: int = 2) -> None:
    raise OperationError(message, code)


def extract_response(text: str) -> dict:
    decoder = json.JSONDecoder()
    for offset, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    fail("protection unreadable (invalid JSON)")


def parse_contexts(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",")]
    if not values or any(not item for item in values):
        fail("protection unreadable (invalid expected contexts)")
    if len(set(values)) != len(values):
        fail("protection unreadable (duplicate expected context)")
    return sorted(values)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def bool_field(data: dict, key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, dict) or not isinstance(value.get("enabled"), bool):
        fail(f"protection unreadable (invalid {key})")
    return value["enabled"]


def redacted_restrictions(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, dict):
        fail("protection unreadable (invalid restrictions)")
    result = {}
    for key in ("users", "teams", "apps"):
        identities = value.get(key, [])
        if not isinstance(identities, list):
            fail(f"protection unreadable (invalid restrictions.{key})")
        result[key] = {"count": len(identities), "digest": digest(identities)}
    return result


def normalized(data: dict) -> dict:
    required = {
        "required_status_checks", "required_pull_request_reviews", "enforce_admins",
        "required_linear_history", "allow_force_pushes", "allow_deletions", "block_creations",
        "required_conversation_resolution", "lock_branch", "allow_fork_syncing",
    }
    missing = sorted(required.difference(data))
    if missing:
        fail("protection unreadable (missing fields: " + ",".join(missing) + ")")

    status = data["required_status_checks"]
    if not isinstance(status, dict) or not isinstance(status.get("strict"), bool):
        fail("protection unreadable (invalid required_status_checks)")
    contexts = status.get("contexts")
    if not isinstance(contexts, list) or any(not isinstance(item, str) for item in contexts):
        fail("protection unreadable (invalid required_status_checks.contexts)")
    if len(set(contexts)) != len(contexts):
        fail("protection unreadable (duplicate required status context)")
    reviews = data["required_pull_request_reviews"]
    if reviews is not None and not isinstance(reviews, dict):
        fail("protection unreadable (invalid required_pull_request_reviews)")
    return {
        "required_pull_request_reviews": reviews,
        "enforce_admins": bool_field(data, "enforce_admins"),
        "required_status_checks": {"strict": status["strict"], "contexts": sorted(contexts)},
        "restrictions": redacted_restrictions(data.get("restrictions")),
        "required_linear_history": bool_field(data, "required_linear_history"),
        "allow_force_pushes": bool_field(data, "allow_force_pushes"),
        "allow_deletions": bool_field(data, "allow_deletions"),
        "block_creations": bool_field(data, "block_creations"),
        "required_conversation_resolution": bool_field(data, "required_conversation_resolution"),
        "lock_branch": bool_field(data, "lock_branch"),
        "allow_fork_syncing": bool_field(data, "allow_fork_syncing"),
    }


def run_gh(endpoint: str, patch_path: Path | None = None) -> str:
    if patch_path is None:
        argv = ["gh", "api", "--include", endpoint]
    else:
        argv = ["gh", "api", endpoint, "-X", "PATCH", "--input", str(patch_path)]
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        suffix = f" (API rc={result.returncode})"
        raise OperationError(f"protection API failed{suffix}", 2)
    return result.stdout


def read_normalized(endpoint: str) -> dict:
    return normalized(extract_response(run_gh(endpoint)))


def fd_identity(descriptor: int) -> tuple[int, int] | None:
    try:
        descriptor_stat = os.fstat(descriptor)
    except OSError:
        return None
    if not stat.S_ISREG(descriptor_stat.st_mode):
        return None
    return descriptor_stat.st_dev, descriptor_stat.st_ino


def path_identity(path: Path) -> tuple[int, int] | None:
    try:
        path_stat = os.lstat(path)
    except OSError:
        return None
    if not stat.S_ISREG(path_stat.st_mode):
        return None
    return path_stat.st_dev, path_stat.st_ino


def path_matches(path: Path, descriptor: int) -> bool:
    descriptor_identity = fd_identity(descriptor)
    return descriptor_identity is not None and path_identity(path) == descriptor_identity


def write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        count = os.write(descriptor, view)
        if count <= 0:
            raise OSError("short write")
        view = view[count:]


def write_fd(descriptor: int, path: Path, payload: str, *, check_path: bool) -> None:
    if fd_identity(descriptor) is None:
        fail("receipt descriptor is not a regular file")
    bound_before = path_matches(path, descriptor)
    if check_path and not bound_before:
        raise PathIdentityError("receipt path identity changed before write")
    try:
        os.fchmod(descriptor, 0o600)
        if check_path and not path_matches(path, descriptor):
            raise PathIdentityError("receipt path identity changed before write")
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.ftruncate(descriptor, 0)
        write_all(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    except PathIdentityError:
        raise
    except OSError as exc:
        raise OperationError(f"receipt write failed: {exc}", 2) from exc
    bound_after = path_matches(path, descriptor)
    if check_path and not bound_after:
        raise PathIdentityError("receipt path identity changed after write")


def safe_unlink(path: Path, descriptor: int | None) -> None:
    try:
        if descriptor is not None and path_matches(path, descriptor):
            os.unlink(path)
    except OSError:
        pass


def close_quietly(descriptor: int | None) -> None:
    if descriptor is None:
        return
    try:
        os.close(descriptor)
    except OSError:
        pass


def action_name(action: str) -> str:
    return "add-required-context" if action == "add" else "remove-required-context"


def incident_payload(
    before: dict | None,
    action: str,
    target: str,
    incident_type: str,
    detail: str,
) -> str:
    incident = {
        "schema": "gac-branch-protection-receipt/v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repo": os.environ.get("GAC_BRANCH_PROTECTION_REPO", "starlink-awaken/omostation"),
        "action": action_name(action),
        "context": target,
        "status": "incomplete",
        "authorization_provenance": "UNPROVABLE",
        "patch_attempted": True,
        "before_digest": before.get("digest") if before else None,
        "patch_body": before.get("patch_body") if before else None,
        "incident": {"type": incident_type, "detail": detail},
        "limitations": [
            "mutation was attempted but final verification or receipt publication did not complete",
            "handled writes are fsynced; SIGKILL, power loss, disk-full, or partial-write failures may still leave residual evidence",
            "residual GET-B/PATCH race cannot be eliminated without a server-side conditional unsafe write",
        ],
    }
    return json.dumps(incident, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_incident(
    receipt_path: Path,
    receipt_descriptor: int | None,
    sidecar_path: Path,
    sidecar_descriptor: int | None,
    before: dict | None,
    action: str,
    target: str,
    incident_type: str,
    detail: str,
) -> None:
    payload = incident_payload(before, action, target, incident_type, detail)
    if receipt_descriptor is not None:
        try:
            write_fd(
                receipt_descriptor,
                receipt_path,
                payload,
                check_path=path_matches(receipt_path, receipt_descriptor),
            )
        except Exception:
            pass
    if sidecar_descriptor is not None:
        try:
            write_fd(
                sidecar_descriptor,
                sidecar_path,
                payload,
                check_path=path_matches(sidecar_path, sidecar_descriptor),
            )
        except Exception:
            pass


def final_payload(before: dict, after: dict, action: str, target: str) -> str:
    receipt = {
        "schema": "gac-branch-protection-receipt/v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repo": os.environ.get("GAC_BRANCH_PROTECTION_REPO", "starlink-awaken/omostation"),
        "action": action_name(action),
        "context": target,
        "before_digest": before["digest"],
        "after_digest": digest(after),
        "before_contexts": before["normalized"]["required_status_checks"]["contexts"],
        "after_contexts": after["required_status_checks"]["contexts"],
        "patch_body": before["patch_body"],
        "preserved_fields": [
            "required_pull_request_reviews", "enforce_admins", "restrictions",
            "required_linear_history", "allow_force_pushes", "allow_deletions",
            "block_creations", "required_conversation_resolution", "lock_branch",
            "allow_fork_syncing",
        ],
        "authorization_provenance": "UNPROVABLE",
        "limitations": [
            "residual GET-B/PATCH race cannot be eliminated without a server-side conditional unsafe write",
            "handled final writes are fsynced; SIGKILL, power loss, disk-full, or partial-write failures may leave residual evidence",
            "no live human authorization or historical mutation provenance is asserted by this tool",
        ],
    }
    return json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def update(receipt_raw: str, expected_raw: str, action: str, target: str, protection_endpoint: str, status_endpoint: str) -> None:
    receipt_path = Path(receipt_raw)
    sidecar_path = Path(str(receipt_path) + ".incident")
    receipt_descriptor: int | None = None
    sidecar_descriptor: int | None = None
    patch_attempted = False
    before: dict | None = None

    try:
        try:
            receipt_descriptor = os.open(receipt_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            os.fchmod(receipt_descriptor, 0o600)
            sidecar_descriptor = os.open(sidecar_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            os.fchmod(sidecar_descriptor, 0o600)
        except OSError as exc:
            raise OperationError(f"receipt reservation failed: {exc}", 2) from exc

        expected = parse_contexts(expected_raw)
        before_normalized = read_normalized(protection_endpoint)
        if not path_matches(receipt_path, receipt_descriptor):
            raise PathIdentityError("receipt path identity changed before GET A verification")
        actual = before_normalized["required_status_checks"]["contexts"]
        if actual != expected:
            raise OperationError(
                "expected contexts mismatch: " + ",".join(actual) + " != " + ",".join(expected),
                1,
            )
        if action == "add":
            if target in expected:
                fail("add expected contexts must not already contain gac-gate")
            desired_contexts = sorted(set(actual) | {target})
        elif action == "remove":
            if target not in expected:
                fail("remove expected contexts must contain gac-gate")
            desired_contexts = sorted(set(actual) - {target})
        else:
            fail("invalid context update action")
        desired = copy.deepcopy(before_normalized)
        desired["required_status_checks"]["contexts"] = desired_contexts
        patch_body = {
            "strict": before_normalized["required_status_checks"]["strict"],
            "contexts": desired_contexts,
        }
        before = {
            "normalized": before_normalized,
            "digest": digest(before_normalized),
            "desired": desired,
            "patch_body": patch_body,
        }

        second = read_normalized(protection_endpoint)
        if not path_matches(receipt_path, receipt_descriptor):
            raise PathIdentityError("receipt path identity changed before GET B verification")
        if digest(second) != before["digest"]:
            raise OperationError(
                "guarded double-read mismatch: A=" + before["digest"] + " B=" + digest(second),
                1,
            )

        payload_path: Path | None = None
        try:
            request_descriptor, request_name = tempfile.mkstemp(prefix="gac-branch-protection-request.")
            payload_path = Path(request_name)
            try:
                os.fchmod(request_descriptor, 0o600)
                write_all(request_descriptor, (json.dumps(patch_body, sort_keys=True, indent=2) + "\n").encode("utf-8"))
                os.fsync(request_descriptor)
            finally:
                os.close(request_descriptor)
            patch_attempted = True
            run_gh(status_endpoint, payload_path)
        except OperationError as exc:
            if patch_attempted:
                write_incident(receipt_path, receipt_descriptor, sidecar_path, sidecar_descriptor, before, action, target, "patch-failed", str(exc))
            raise
        except OSError as exc:
            if patch_attempted:
                write_incident(receipt_path, receipt_descriptor, sidecar_path, sidecar_descriptor, before, action, target, "patch-failed", f"PATCH request failed: {exc}")
            raise OperationError(f"PATCH request preparation failed: {exc}", 2) from exc
        finally:
            if payload_path is not None:
                try:
                    os.unlink(payload_path)
                except OSError:
                    pass

        try:
            after = read_normalized(protection_endpoint)
            if not path_matches(receipt_path, receipt_descriptor):
                raise PathIdentityError("receipt path identity changed after PATCH")
            if after != desired:
                raise OperationError("GET C full-protection verification failed", 1)
            write_fd(receipt_descriptor, receipt_path, final_payload(before, after, action, target), check_path=True)
            if not path_matches(sidecar_path, sidecar_descriptor):
                raise PathIdentityError("incident sidecar path identity changed before cleanup")
            os.unlink(sidecar_path)
        except OperationError as exc:
            incident_type = "get-c-non-context-drift" if exc.code == 1 else "get-c-failed"
            if isinstance(exc, PathIdentityError):
                incident_type = "receipt-path-identity-mismatch"
            write_incident(receipt_path, receipt_descriptor, sidecar_path, sidecar_descriptor, before, action, target, incident_type, str(exc))
            raise
        except OSError as exc:
            write_incident(receipt_path, receipt_descriptor, sidecar_path, sidecar_descriptor, before, action, target, "receipt-publication-failed", str(exc))
            raise OperationError(f"final receipt publication failed: {exc}", 2) from exc
        except Exception as exc:
            write_incident(receipt_path, receipt_descriptor, sidecar_path, sidecar_descriptor, before, action, target, "receipt-publication-failed", str(exc))
            raise OperationError(f"final receipt publication failed: {exc}", 2) from exc
    except OperationError:
        if not patch_attempted:
            safe_unlink(receipt_path, receipt_descriptor)
            safe_unlink(sidecar_path, sidecar_descriptor)
        raise
    finally:
        if not patch_attempted:
            safe_unlink(receipt_path, receipt_descriptor)
            safe_unlink(sidecar_path, sidecar_descriptor)
        close_quietly(sidecar_descriptor)
        close_quietly(receipt_descriptor)


operation = sys.argv[1]
try:
    if operation == "check":
        current = normalized(extract_response(Path(sys.argv[2]).read_text(encoding="utf-8")))
        expected = parse_contexts(sys.argv[3])
        actual = current["required_status_checks"]["contexts"]
        print("  Required status checks: " + (",".join(actual) or "none"))
        print("  Expected status checks: " + (",".join(expected) or "none"))
        if actual != expected:
            print("❌ protection drift")
            raise SystemExit(1)
        print("✅ protection aligned")
    elif operation == "update":
        update(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7])
        print("✅ guarded context update complete")
    else:
        fail("unknown parser operation")
except OperationError as exc:
    print(f"❌ {exc}", file=sys.stderr)
    raise SystemExit(exc.code)
except SystemExit:
    raise
except Exception as exc:
    print(f"❌ protection tool failure: {exc}", file=sys.stderr)
    raise SystemExit(2)
PY
}

check_protection() {
  local temporary rc
  temporary="$(mktemp "${TMPDIR:-/tmp}/gac-protection-check.XXXXXX")"
  if get_protection "$temporary"; then
    set +e
    python_tool check "$temporary" "$expected_contexts"
    rc=$?
    set -e
  else
    rc=$?
  fi
  rm -f -- "$temporary" || true
  return "$rc"
}

guarded_update() {
  confirm_action "confirm only $1 gac-gate required context" || return 1
  python_tool update "$receipt" "$expected_contexts" "$1" "$target" "$PROTECTION_ENDPOINT" "$STATUS_ENDPOINT"
}

case "$mode" in
  check)
    check_protection
    ;;
  add|remove)
    guarded_update "$mode"
    ;;
  *)
    echo "❌ internal command error" >&2
    exit 2
    ;;
esac
