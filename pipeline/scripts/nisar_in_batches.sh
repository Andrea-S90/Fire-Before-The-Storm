#!/usr/bin/env bash
# NISAR for small disks: download one pass, grid it (step 04), delete its raw files, next pass.
# All passes together are ~70 GB of raw files; this way the peak is one pass (~20 GB) and what stays
# is the gridded stack (~2 GB). Run from pipeline/ with the environment active and internet available:
#   bash scripts/nisar_in_batches.sh              # every pass in the search result
#   PASSES="087A 095D" bash scripts/nisar_in_batches.sh
# A pass's raw files are deleted only after every one of its dates is in work/nisar/index.csv.
set -euo pipefail
cd "$(dirname "$0")/.."
DATA=$(python -c "import sys; sys.path.insert(0, '.'); from ashwatch.common import load_config; print(load_config()['_root'])")
RAW=$DATA/raw/nisar
INDEX=$DATA/work/nisar/index.csv

python steps/01_download_nisar.py --dry-run
PASSES=${PASSES:-$(tail -n +2 "$RAW/manifest.csv" | awk -F, '{print $2 $3}' | sort -u | tr '\n' ' ')}
echo "Passes: $PASSES"

for P in $PASSES; do
  echo "=== $(date +%T) pass $P: download"
  python steps/01_download_nisar.py --passes "$P"
  echo "=== $(date +%T) pass $P: grid"
  python steps/04_nisar_stack.py
  MISSING=$(tail -n +2 "$RAW/manifest.csv" | cut -d, -f1 | sort -u | while read -r D; do
              grep -q "^$D,$P," "$INDEX" || echo "$D"; done)
  if [ -n "$MISSING" ]; then
    echo "Pass $P: these dates are not in the stack, raw files kept: $MISSING" >&2
    exit 1
  fi
  rm -f "$RAW"/NISAR_L2_*_GCOV_???_"${P:0:3}"_"${P:3:1}"_*.h5
  echo "=== $(date +%T) pass $P: done, raw files removed ($(du -sh "$DATA" | cut -f1) used)"
done
echo "All passes gridded: $(($(wc -l < "$INDEX") - 1)) dates x passes in $INDEX"
