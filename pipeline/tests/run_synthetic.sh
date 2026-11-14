#!/usr/bin/env bash
# End-to-end smoke test on fake data (no internet, ~2-5 minutes). From the pipeline/ folder:
#   bash tests/run_synthetic.sh /tmp/aw_test
set -euo pipefail
ROOT=${1:-/tmp/aw_test}
cd "$(dirname "$0")/.."
python tests/make_synthetic.py "$ROOT"
export ASHWATCH_CONFIG=$ROOT/synthetic.yaml
for s in 03 04 05 06 07 08 09 10 11 12; do
  echo "=== step $s"
  python steps/${s}_*.py
done
python steps/inspect_gcov.py "$(ls $ROOT/data/raw/nisar/*_PR_*.h5 | head -1)" | tail -4
echo "OK: web files in $ROOT/web"
ls -la "$ROOT/web" "$ROOT/web/img"
