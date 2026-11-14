#!/bin/bash
#SBATCH --job-name=ashwatch
#SBATCH --qos=bbdefault
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=3:0:0
#SBATCH --output=logs/process_%j.log
# Processing steps 03-12 on BlueBEAR (no internet needed once the environment exists). From pipeline/:
#   sbatch slurm/bluebear_process.sbatch
#   sbatch --export=ALL,STEPS="03 04" slurm/bluebear_process.sbatch          # only some steps
set -eo pipefail
module purge; module load bluebear
cd "${SLURM_SUBMIT_DIR:-.}"
source slurm/bluebear_env.sh
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8}
export GDAL_CACHEMAX=2048

STEPS=${STEPS:-"03 04 05 06 07 08 09 10 11 12"}
for s in $STEPS; do
  f=$(ls steps/${s}_*.py)
  echo "=== $(date +%T) $f"
  python "$f"
done
echo "=== $(date +%T) all done; web files in ${ASHWATCH_WEB_OUT:-../web/public/data}"
