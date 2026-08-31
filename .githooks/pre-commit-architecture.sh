#!/bin/bash
echo "Running architecture checks..."
python3 bin/ssot/scene-card-lifecycle.py --validate --all 2>/dev/null || true
python3 bin/gac/architecture-check.py --quick || true
echo "Architecture checks completed!"
