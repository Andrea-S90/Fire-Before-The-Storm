#!/usr/bin/env bash
# All downloads with the Python steps. Run on a node with internet (usually the login or transfer node):
#   nohup bash scripts/run_downloads.sh > logs/downloads.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
python steps/01_download_nisar.py --dry-run          # writes data/raw/nisar/urls.txt first
python steps/02_download_ancillary.py dem s2 cci soil osm era5 imerg wtd
python steps/01_download_nisar.py                     # the big one last (tens of GB)
echo "Downloads finished: $(date)"
