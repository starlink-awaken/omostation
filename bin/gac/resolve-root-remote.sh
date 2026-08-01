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

# Canonical root repository used by git and gh operations.
CANONICAL_ROOT_REPO="starlink-awaken/omostation"

resolve_root_remote() {
  # 1. Explicit env var
  if [ -n "${OMOSTATION_ROOT_REMOTE:-}" ]; then
    local remote_url
    remote_url=$(git remote get-url "$OMOSTATION_ROOT_REMOTE" 2>/dev/null) || {
      echo "❌ OMOSTATION_ROOT_REMOTE='$OMOSTATION_ROOT_REMOTE' is not a valid git remote" >&2
      return 1
    }
    if _remote_matches_canonical "$OMOSTATION_ROOT_REMOTE"; then
      echo "$OMOSTATION_ROOT_REMOTE"
      return 0
    else
      echo "❌ OMOSTATION_ROOT_REMOTE='$OMOSTATION_ROOT_REMOTE' URL '$remote_url' does not match canonical root repo" >&2
      return 1
    fi
  fi

  # 2. Named remote "omostation-root"
  if git remote get-url omostation-root &>/dev/null; then
    if _remote_matches_canonical "omostation-root"; then
      echo "omostation-root"
      return 0
    fi
  fi

  # 3. URL match across all remotes
  local remote
  for remote in $(git remote 2>/dev/null); do
    if _remote_matches_canonical "$remote"; then
      echo "$remote"
      return 0
    fi
  done

  # 4. Fail closed
  echo "❌ No remote found pointing to starlink-awaken/omostation (canonical root repo)" >&2
  echo "   Available remotes:" >&2
  git remote -v 2>/dev/null | sed 's/^/     /' >&2
  echo "   Expected: remote whose fetch and push URLs both resolve to '$CANONICAL_ROOT_REPO'" >&2
  echo "   Fix: git remote add omostation-root https://github.com/starlink-awaken/omostation.git" >&2
  return 1
}

_remote_matches_canonical() {
  local remote="$1"
  local fetch_url push_url
  fetch_url=$(git remote get-url "$remote" 2>/dev/null) || return 1
  push_url=$(git remote get-url --push "$remote" 2>/dev/null) || return 1
  _url_matches_canonical "$fetch_url" && _url_matches_canonical "$push_url"
}

_url_matches_canonical() {
  local url="$1"
  # Accept only exact GitHub host/repository forms; reject lookalike hosts and paths.
  case "$url" in
    "https://github.com/$CANONICAL_ROOT_REPO"|"https://github.com/$CANONICAL_ROOT_REPO.git"|"https://github.com/$CANONICAL_ROOT_REPO/"|"https://github.com/$CANONICAL_ROOT_REPO.git/") return 0 ;;
    "http://github.com/$CANONICAL_ROOT_REPO"|"http://github.com/$CANONICAL_ROOT_REPO.git"|"http://github.com/$CANONICAL_ROOT_REPO/"|"http://github.com/$CANONICAL_ROOT_REPO.git/") return 0 ;;
    "ssh://git@github.com/$CANONICAL_ROOT_REPO"|"ssh://git@github.com/$CANONICAL_ROOT_REPO.git"|"ssh://git@github.com/$CANONICAL_ROOT_REPO/"|"ssh://git@github.com/$CANONICAL_ROOT_REPO.git/") return 0 ;;
    "git@github.com:$CANONICAL_ROOT_REPO"|"git@github.com:$CANONICAL_ROOT_REPO.git"|"git@github.com:$CANONICAL_ROOT_REPO/"|"git@github.com:$CANONICAL_ROOT_REPO.git/") return 0 ;;
    *) return 1 ;;
  esac
}
