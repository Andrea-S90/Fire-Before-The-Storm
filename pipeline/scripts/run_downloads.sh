#!/usr/bin/env bash
# All downloads with the Python steps (needs about 100 GB free; see scripts/nisar_in_batches.sh for less):
#   nohup bash scripts/run_downloads.sh > logs/downloads.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
python steps/01_download_nisar.py --dry-run          # writes data/raw/nisar/urls.txt first
python steps/02_download_ancillary.py dem s2 cci soil osm imerg wtd
python steps/01_download_nisar.py                     # the big one (tens of GB)
python steps/02_download_ancillary.py era5            # last: the CDS queues requests, sometimes for hours
echo "Downloads finished: $(date)"
