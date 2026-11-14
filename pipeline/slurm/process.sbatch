#!/usr/bin/env bash
#SBATCH --job-name=ashwatch
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=logs/ashwatch_%j.log
# Processing steps 03-12 (no internet needed). Submit from the pipeline/ folder:
#   mkdir -p logs && sbatch slurm/process.sbatch
# Run a subset:  sbatch --export=ALL,STEPS="07 08 09 10 11 12" slurm/process.sbatch
set -euo pipefail
# --- adapt to your cluster ---
# module load miniforge3
# source activate ashwatch            # or: source ~/venvs/ashwatch/bin/activate
# export ASHWATCH_DATA=/scratch/$USER/ashwatch
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export GDAL_CACHEMAX=2048

STEPS=${STEPS:-"03 04 05 06 07 08 09 10 11 12"}
for s in $STEPS; do
  f=$(ls steps/${s}_*.py)
  echo "=== $(date +%T) $f"
  python "$f"
done
echo "=== $(date +%T) all done; web files in ${ASHWATCH_WEB_OUT:-../web/public/data}"
