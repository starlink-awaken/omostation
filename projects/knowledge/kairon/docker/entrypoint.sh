#!/bin/bash
# kairon E2E Test Entrypoint
# Used in CI to orchestrate containerized E2E test execution.
#
# Usage:
#   ./docker/entrypoint.sh              # Run all E2E tests
#   ./docker/entrypoint.sh --coverage   # Run with coverage
#   ./docker/entrypoint.sh --subset core  # Run core path tests only

set -euo pipefail

E2E_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${E2E_DIR}/docker/docker-compose.e2e.yml"

COVERAGE=false
SUBSET="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --coverage) COVERAGE=true; shift ;;
        --subset) SUBSET="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cleanup() {
    echo "=== Cleaning up E2E environment ==="
    docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Starting E2E test environment ==="
docker compose -f "$COMPOSE_FILE" build kairon-e2e
docker compose -f "$COMPOSE_FILE" up -d postgres

echo "=== Running E2E tests ==="
if [ "$COVERAGE" = true ]; then
    docker compose -f "$COMPOSE_FILE" run --rm kairon-e2e \
        uv run --no-sync pytest packages/*/tests/ \
        -v --timeout=60 -q --tb=short \
        -p no:cacheprovider --cov=packages --cov-report=term
elif [ "$SUBSET" = "core" ]; then
    # Run the stable container smoke path first: ontoderive end-to-end.
    docker compose -f "$COMPOSE_FILE" run --rm kairon-e2e \
        uv run --no-sync pytest packages/ontoderive/tests/test_e2e.py \
        -v --timeout=60 -q --tb=short -p no:cacheprovider
else
    docker compose -f "$COMPOSE_FILE" run --rm kairon-e2e \
        uv run --no-sync pytest packages/*/tests/ \
        -v --timeout=60 -q --tb=short -p no:cacheprovider
fi

echo "=== E2E tests completed ==="
