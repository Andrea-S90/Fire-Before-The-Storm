#!/bin/bash
#SBATCH --job-name=ashwatch-dl
#SBATCH --qos=bbdefault
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=24:0:0
#SBATCH --output=logs/download_%j.log
# All downloads as a batch job. Only works if the smoke test printed "INTERNET: yes".
# Needs ~/.netrc and ~/.cdsapirc (scripts/setup_credentials.sh). Resumable: just submit again.
#   sbatch slurm/bluebear_download.sbatch
#   sbatch --export=ALL,NISAR_MAX_FILES=2 slurm/bluebear_download.sbatch     # small first test
set -eo pipefail
module purge; module load bluebear
cd "${SLURM_SUBMIT_DIR:-.}"
source slurm/bluebear_env.sh

if [ -n "${NISAR_MAX_FILES:-}" ]; then
  python steps/02_download_ancillary.py dem s2 cci soil osm era5 imerg wtd || echo "some ancillary sources failed (see above)"
  python steps/01_download_nisar.py --max-files "$NISAR_MAX_FILES"
  python steps/inspect_gcov.py "$(ls "$ASHWATCH_DATA"/raw/nisar/*_PR_GCOV_*.h5 | head -1)"
else
  bash scripts/run_downloads.sh
fi
du -sh "$ASHWATCH_DATA"/raw/* || true
