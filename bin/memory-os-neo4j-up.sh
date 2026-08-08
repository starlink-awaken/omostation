#!/usr/bin/env bash
# Start Neo4j for Memory OS: Docker preferred → brew fallback.
# Usage: bash bin/memory-os-neo4j-up.sh [--status|--stop]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOS_COMPOSE="${ROOT}/projects/kairon/packages/mos/docker-compose.yml"
MINERVA_COMPOSE_DIR="${ROOT}/projects/kairon/packages/minerva/docker"
PASS="${NEO4J_PASSWORD:-changeme}"
URI="${NEO4J_URI:-bolt://localhost:7687}"
USER="${NEO4J_USER:-neo4j}"

# Prefer Podman machine socket when Docker Desktop is dead
_try_podman_host() {
  if [[ -n "${DOCKER_HOST:-}" ]]; then
    return 0
  fi
  local sock
  sock="$(podman machine inspect mos-neo4j --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null || true)"
  if [[ -z "$sock" ]]; then
    sock="$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null | head -1 || true)"
  fi
  if [[ -n "$sock" && -S "$sock" ]]; then
    export DOCKER_HOST="unix://$sock"
    echo "using DOCKER_HOST=$DOCKER_HOST (podman)"
  fi
}

docker_ok() {
  _try_podman_host
  # 4s hard cap — Docker Desktop I/O hang is common
  if command -v perl >/dev/null 2>&1; then
    perl -e 'alarm 4; exec @ARGV' docker info >/dev/null 2>&1
  else
    docker info >/dev/null 2>&1
  fi
}

probe_bolt() {
  if command -v cypher-shell >/dev/null 2>&1; then
    echo 'RETURN 1 AS ok;' | cypher-shell -a "$URI" -u "$USER" -p "$PASS" --format plain >/dev/null 2>&1
  else
    nc -z 127.0.0.1 7687 2>/dev/null
  fi
}

cmd_status() {
  echo "NEO4J_URI=$URI"
  if probe_bolt; then
    echo "bolt: UP"
  else
    echo "bolt: DOWN"
  fi
  if docker_ok; then
    docker ps --filter name=mos-neo4j --filter name=minerva-neo4j --format 'docker: {{.Names}} {{.Status}}' 2>/dev/null || true
  else
    echo "docker: DOWN"
  fi
  if command -v neo4j >/dev/null 2>&1; then
    neo4j status 2>/dev/null || true
  fi
}

cmd_stop() {
  if docker_ok; then
    docker rm -f mos-neo4j 2>/dev/null || true
    if [[ -f "$MINERVA_COMPOSE_DIR/docker-compose.yml" ]]; then
      (cd "$MINERVA_COMPOSE_DIR" && docker compose --profile full stop neo4j 2>/dev/null) || true
    fi
  fi
  if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -q '^neo4j'; then
    brew services stop neo4j 2>/dev/null || true
  fi
  echo "stopped (best-effort)"
}

cmd_up() {
  if probe_bolt; then
    echo "already up: $URI"
    echo "export NEO4J_URI=$URI NEO4J_USER=$USER NEO4J_PASSWORD=$PASS"
    return 0
  fi

  if docker_ok; then
    echo "docker OK — starting mos-neo4j compose"
    docker compose -f "$MOS_COMPOSE" up -d
    for i in $(seq 1 40); do
      if docker inspect -f '{{.State.Health.Status}}' mos-neo4j 2>/dev/null | grep -q healthy; then
        break
      fi
      if probe_bolt; then
        break
      fi
      sleep 2
    done
    if probe_bolt; then
      echo "OK via docker mos-neo4j"
      echo "export NEO4J_URI=$URI NEO4J_USER=$USER NEO4J_PASSWORD=$PASS"
      return 0
    fi
    echo "WARN: docker started but bolt not ready; try brew fallback"
  else
    echo "docker unavailable — brew fallback"
  fi

  if ! command -v neo4j >/dev/null 2>&1; then
    echo "installing neo4j via brew..."
    brew install neo4j
  fi
  brew services start neo4j
  for i in $(seq 1 30); do
    if nc -z 127.0.0.1 7687 2>/dev/null; then
      break
    fi
    sleep 2
  done
  # first-run password change neo4j → changeme
  if ! probe_bolt; then
    if command -v uv >/dev/null 2>&1; then
      NEO4J_URI="$URI" uv run --with neo4j python - <<'PY' || true
from neo4j import GraphDatabase
import os
uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
try:
    d = GraphDatabase.driver(uri, auth=("neo4j", "neo4j"))
    with d.session(database="system") as s:
        s.run("ALTER CURRENT USER SET PASSWORD FROM $o TO $n", o="neo4j", n="changeme")
    d.close()
    print("password set to changeme")
except Exception as e:
    print("password change skipped:", e)
PY
    fi
  fi
  if probe_bolt; then
    echo "OK via brew neo4j"
    echo "export NEO4J_URI=$URI NEO4J_USER=$USER NEO4J_PASSWORD=$PASS"
    return 0
  fi
  echo "FAIL: could not bring Neo4j up"
  return 1
}

case "${1:-up}" in
  up) cmd_up ;;
  status|--status) cmd_status ;;
  stop|--stop) cmd_stop ;;
  *)
    echo "usage: $0 [up|status|stop]"
    exit 2
    ;;
esac
