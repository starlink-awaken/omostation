#!/bin/bash
# Workspace hardcoded config scanner
WORKSPACE="/Users/xiamingxing/Workspace"

PROJECTS=(
  "SharedBrain" "kos" "minerva" "agentmesh" "gstack" "wps-skills"
  "Forge" "codeanalyze" "MetaOS" "agora" "sophia" "kronos"
  "eCOS" "ontoderive" "pallas" "eidos" "iris" "hermes-webui"
  "gbrain-repo" "wksp" "gateway" "bos-skill-cli" "agent-runtime"
)

EXCLUDE="-not -path '*/.git/*' -not -path '*/__pycache__/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/venv/*' -not -path '*.egg-info/*' -not -path '*/dist/*' -not -path '*/build/*' -not -path '*/_archived/*'"

EXTENSIONS="-name '*.py' -o -name '*.sh' -o -name '*.ts' -o -name '*.json' -o -name '*.yaml' -o -name '*.yml' -o -name '*.toml' -o -name '*.cfg' -o -name '*.env*' -o -name '*.md' -o -name 'Dockerfile*' -o -name 'Makefile' -o -name '*.conf'"

echo "=== HARDCODED CONFIG SCAN REPORT ==="
echo "Generated: $(date)"
echo "====================================="
echo ""

SCAN_DIRS=("$@")
if [ ${#SCAN_DIRS[@]} -eq 0 ]; then
  for PROJ in "${PROJECTS[@]}"; do
    if [ -d "$WORKSPACE/$PROJ" ]; then
      SCAN_DIRS+=("$WORKSPACE/$PROJ")
    fi
  done
fi

for DIR in "${SCAN_DIRS[@]}"; do
  PROJ_NAME=$(basename "$DIR")
  echo "----------------------------------------------------------------------"
  echo "## Project: $PROJ_NAME (cd $DIR)"
  echo ""
  
  # 1. Absolute paths (/Users/xiamingxing)
  ABS_COUNT=$(find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -l "/Users/xiamingxing" {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$ABS_COUNT" -gt 0 ] && [ "$ABS_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [PATH] Absolute paths (/Users/xiamingxing):"
    find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -Hn "/Users/xiamingxing" {} \; 2>/dev/null | head -20 | sed 's|/Users/xiamingxing/Workspace/||g' | sed 's|/Users/xiamingxing|~|g'
  fi
  
  # 2. Tilde paths
  TILDE_COUNT=$(find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -l '~/' {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$TILDE_COUNT" -gt 0 ] && [ "$TILDE_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [PATH] Tilde paths (~/):"
    find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -Hn '~/' {} \; 2>/dev/null | grep -v '__pycache__' | grep -v 'node_modules' | grep -v '.git/' | grep -v '"~/' | head -15 | sed "s|$WORKSPACE/||g"
  fi
  
  # 3. Hardcoded ports
  PORT_COUNT=$(find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -lE 'localhost:[0-9]{4}' {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$PORT_COUNT" -gt 0 ] && [ "$PORT_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [PORT] Hardcoded localhost ports:"
    find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -HnE 'localhost:[0-9]{2,5}' {} \; 2>/dev/null | head -20 | sed "s|$WORKSPACE/||g"
  fi
  
  # Also check 127.0.0.1 ports
  IP_PORT_COUNT=$(find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -lE '127\.0\.0\.1:[0-9]{2,5}' {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$IP_PORT_COUNT" -gt 0 ] && [ "$IP_PORT_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [PORT] Hardcoded 127.0.0.1:port:"
    find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -HnE '127\.0\.0\.1:[0-9]{2,5}' {} \; 2>/dev/null | head -10 | sed "s|$WORKSPACE/||g"
  fi
  
  # 4. Database paths
  DB_COUNT=$(find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -lE '\.db["\x27\s\)]|sqlite:///|\.sqlite' {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$DB_COUNT" -gt 0 ] && [ "$DB_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [DB] Database references:"
    find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -HnE '\.db["\x27\s\)]|sqlite:///|\.sqlite' {} \; 2>/dev/null | head -15 | sed "s|$WORKSPACE/||g"
  fi
  
  # 5. Tool calls - subprocess/curl/python3 ...py references
  SUBCALL_COUNT=$(find "$DIR" $EXCLUDE \( -name '*.py' -o -name '*.sh' -o -name '*.ts' \) -exec grep -lE 'subprocess\.(call|run|Popen|check_call|check_output)' {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$SUBCALL_COUNT" -gt 0 ] && [ "$SUBCALL_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [TOOL] subprocess calls:"
    find "$DIR" $EXCLUDE \( -name '*.py' -o -name '*.sh' -o -name '*.ts' \) -exec grep -HnE 'subprocess\.(call|run|Popen|check_call|check_output)' {} \; 2>/dev/null | head -15 | sed "s|$WORKSPACE/||g"
  fi
  
  # 6. ~/.hermes references
  HERMES_COUNT=$(find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -l '\.hermes' {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$HERMES_COUNT" -gt 0 ] && [ "$HERMES_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [HERMES] ~/.hermes/ references:"
    find "$DIR" $EXCLUDE \( $EXTENSIONS \) -exec grep -Hn '\.hermes' {} \; 2>/dev/null | head -15 | sed "s|$WORKSPACE/||g"
  fi
  
  # 7. ENV vars with default values
  ENV_COUNT=$(find "$DIR" $EXCLUDE \( -name '*.py' -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' -o -name '*.env*' -o -name '*.sh' \) -exec grep -lE 'os\.environ\.get\(.*default|os\.getenv\(.*, |env\(.*default' {} \; 2>/dev/null | wc -l | tr -d ' ')
  if [ "$ENV_COUNT" -gt 0 ] && [ "$ENV_COUNT" -gt 0 ] 2>/dev/null; then
    echo ">>> [ENV] Env vars with defaults:"
    find "$DIR" $EXCLUDE \( -name '*.py' -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' -o -name '*.env*' -o -name '*.sh' \) -exec grep -HnE 'os\.environ\.get\(.*default|os\.getenv\(.*, |env\(.*default' {} \; 2>/dev/null | head -20 | sed "s|$WORKSPACE/||g"
  fi
  
  echo ""
done
