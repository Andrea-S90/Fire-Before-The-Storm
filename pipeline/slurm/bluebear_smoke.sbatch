#!/bin/bash
#SBATCH --job-name=ashwatch-smoke
#SBATCH --qos=bbdefault
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=30:0
#SBATCH --output=logs/smoke_%j.log
# BlueBEAR smoke test: builds the environment if needed, reports whether this compute node has internet,
# then runs the whole chain (steps 03-12) on fake data. Submit from pipeline/:
#   mkdir -p logs && sbatch slurm/bluebear_smoke.sbatch        # add --account=<project> if you have several
set -eo pipefail
module purge; module load bluebear
cd "${SLURM_SUBMIT_DIR:-.}"

if curl -sS -m 20 -o /dev/null -I https://nisar.asf.earthdatacloud.nasa.gov 2>/dev/null; then
  echo "INTERNET: yes (downloads can run as a batch job: slurm/bluebear_download.sbatch)"
else
  echo "INTERNET: no (run scripts/run_downloads.sh on a login node instead)"
fi

source slurm/bluebear_env.sh
ROOT=$(mktemp -d "${TMPDIR:-/tmp}/aw_test.XXXXXX")
trap 'rm -rf "$ROOT"' EXIT
env -u ASHWATCH_DATA bash tests/run_synthetic.sh "$ROOT"
echo "SMOKE TEST PASSED"
