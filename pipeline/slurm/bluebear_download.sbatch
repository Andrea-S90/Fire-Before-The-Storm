#!/bin/bash
#SBATCH --job-name=ashwatch-dl
#SBATCH --qos=bbdefault
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:0:0
#SBATCH --output=logs/download_%j.log
# All downloads as a batch job. Only works if the smoke test printed "INTERNET: yes".
# Needs ~/.netrc and ~/.cdsapirc (scripts/setup_credentials.sh). Resumable: just submit again.
#   sbatch slurm/bluebear_download.sbatch
#   sbatch --export=ALL,NISAR_MAX_FILES=2 slurm/bluebear_download.sbatch     # small first test
#   sbatch --export=ALL,NISAR_BATCHES=1 slurm/bluebear_download.sbatch       # under ~90 GB free: pass by pass,
#                                                                            # gridding and deleting raw files
set -eo pipefail
module purge; module load bluebear
cd "${SLURM_SUBMIT_DIR:-.}"
source slurm/bluebear_env.sh

if [ -n "${NISAR_MAX_FILES:-}" ]; then
  python steps/02_download_ancillary.py dem s2 cci soil osm imerg wtd era5 || echo "some ancillary sources failed (see above)"
  python steps/01_download_nisar.py --max-files "$NISAR_MAX_FILES"
  python steps/inspect_gcov.py "$(ls "$ASHWATCH_DATA"/raw/nisar/*_PR_GCOV_*.h5 | head -1)"
elif [ -n "${NISAR_BATCHES:-}" ]; then
  python steps/02_download_ancillary.py dem s2 cci soil osm imerg wtd || echo "some ancillary sources failed (see above)"
  bash scripts/nisar_in_batches.sh
  # ERA5 last: the CDS queues requests, sometimes for hours, and nothing else should wait for it
  python steps/02_download_ancillary.py era5 || echo "ERA5 failed (see above); re-run: python steps/02_download_ancillary.py era5"
else
  bash scripts/run_downloads.sh
fi
du -sh "$ASHWATCH_DATA"/raw/* || true
