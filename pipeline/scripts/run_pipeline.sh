#!/usr/bin/env bash
# Run the processing steps (no internet needed). From the pipeline/ folder, with the environment active:
#   bash scripts/run_pipeline.sh                  # steps 03-12
#   bash scripts/run_pipeline.sh 10 11 12         # only some steps
#   bash scripts/run_pipeline.sh 03 05 06 07 08 09 10 11 12    # after scripts/nisar_in_batches.sh (it already ran 04)
# Stops at the first step that fails. Logs go to logs/pipeline_<date>.log as well as the screen.
# ASHWATCH_WORKERS=4 limits the parallel processes (default: all cores).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
LOG=logs/pipeline_$(date +%Y%m%d_%H%M%S).log
export OMP_NUM_THREADS=${ASHWATCH_WORKERS:-${OMP_NUM_THREADS:-4}}
export GDAL_CACHEMAX=${GDAL_CACHEMAX:-2048}

STEPS=${*:-"03 04 05 06 07 08 09 10 11 12"}
for s in $STEPS; do
  f=$(ls steps/"${s}"_*.py)
  echo "=== $(date +%T) $f" | tee -a "$LOG"
  python "$f" 2>&1 | tee -a "$LOG"
done
echo "=== $(date +%T) all done; log in $LOG" | tee -a "$LOG"
