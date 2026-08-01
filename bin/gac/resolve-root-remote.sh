#!/bin/bash
# resolve-root-remote.sh — Canonical root remote resolution for omostation
#
# Resolves the correct git remote pointing to starlink-awaken/omostation.
# Priority: explicit $OMOSTATION_ROOT_REMOTE env → named remote "omostation-root"
# → URL match → fail closed.
#
# Usage:
#   source resolve-root-remote.sh
#   ROOT_REMOTE=$(resolve_root_remote)
#
# Exit codes:
#   0 — resolved successfully
#   1 — no valid remote found (fail closed)

# Canonical URL patterns for the root repo
CANONICAL_URL_PATTERNS=(
  "github.com/starlink-awaken/omostation"
  "github.com:starlink-awaken/omostation"
)

resolve_root_remote() {
  # 1. Explicit env var
  if [ -n "${OMOSTATION_ROOT_REMOTE:-}" ]; then
    local remote_url
    remote_url=$(git remote get-url "$OMOSTATION_ROOT_REMOTE" 2>/dev/null) || {
      echo "❌ OMOSTATION_ROOT_REMOTE='$OMOSTATION_ROOT_REMOTE' is not a valid git remote" >&2
      return 1
    }
    if _url_matches_canonical "$remote_url"; then
      echo "$OMOSTATION_ROOT_REMOTE"
      return 0
    else
      echo "❌ OMOSTATION_ROOT_REMOTE='$OMOSTATION_ROOT_REMOTE' URL '$remote_url' does not match canonical root repo" >&2
      return 1
    fi
  fi

  # 2. Named remote "omostation-root"
  if git remote get-url omostation-root &>/dev/null; then
    local remote_url
    remote_url=$(git remote get-url omostation-root)
    if _url_matches_canonical "$remote_url"; then
      echo "omostation-root"
      return 0
    fi
  fi

  # 3. URL match across all remotes
  local remote
  for remote in $(git remote 2>/dev/null); do
    local remote_url
    remote_url=$(git remote get-url "$remote" 2>/dev/null) || continue
    if _url_matches_canonical "$remote_url"; then
      echo "$remote"
      return 0
    fi
  done

  # 4. Fail closed
  echo "❌ No remote found pointing to starlink-awaken/omostation (canonical root repo)" >&2
  echo "   Available remotes:" >&2
  git remote -v 2>/dev/null | sed 's/^/     /' >&2
  echo "   Expected: remote with URL containing 'starlink-awaken/omostation'" >&2
  echo "   Fix: git remote add omostation-root https://github.com/starlink-awaken/omostation.git" >&2
  return 1
}

_url_matches_canonical() {
  local url="$1"
  # Strip .git suffix and trailing slashes for comparison
  local cleaned_url="${url%.git}"
  cleaned_url="${cleaned_url%/}"
  local pattern
  for pattern in "${CANONICAL_URL_PATTERNS[@]}"; do
    local cleaned_pattern="${pattern%.git}"
    cleaned_pattern="${cleaned_pattern%/}"
    # Match URL ending with /<pattern> or @<pattern> (SSH user@host:path)
    # e.g. "/omostation" matches but "/omostation-runtime" does not
    if [[ "$cleaned_url" == *"/$cleaned_pattern" ]] || \
       [[ "$cleaned_url" == *"@$cleaned_pattern" ]]; then
      return 0
    fi
  done
  return 1
}
