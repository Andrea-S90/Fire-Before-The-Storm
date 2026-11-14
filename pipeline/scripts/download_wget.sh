#!/usr/bin/env bash
# Command-line (wget) route for the downloads, for clusters where you prefer not to use the Python steps.
# Run from the pipeline/ folder on a node with internet (login or data-transfer node):
#   bash scripts/download_wget.sh            # all sources that work with plain wget
#   bash scripts/download_wget.sh nisar      # one source
# Needs ~/.netrc with Earthdata credentials (scripts/setup_credentials.sh) for nisar and imerg.
# ERA5 has no wget route: use  python steps/02_download_ancillary.py era5
set -euo pipefail
DATA=${ASHWATCH_DATA:-../data}
RAW=$DATA/raw
BBOX_W=-5.05; BBOX_S=40.15; BBOX_E=-4.25; BBOX_N=40.60      # keep in sync with config/avila.yaml
START=2026-06-17; END=2026-11-14
EDL="--load-cookies $HOME/.urs_cookies --save-cookies $HOME/.urs_cookies --keep-session-cookies --auth-no-challenge=on"
# Token alternative to ~/.netrc:  EDL="--header=Authorization: Bearer $EARTHDATA_TOKEN"
WANT=${1:-all}
run() { [ "$WANT" = all ] || [ "$WANT" = "$1" ]; }

if run nisar; then
  mkdir -p "$RAW/nisar"
  # 1) search the ASF catalogue (no login needed) and keep standard (PR) GCOV product URLs
  POLY="POLYGON(($BBOX_W%20$BBOX_S,$BBOX_E%20$BBOX_S,$BBOX_E%20$BBOX_N,$BBOX_W%20$BBOX_N,$BBOX_W%20$BBOX_S))"
  wget -q -O "$RAW/nisar/search.csv" \
    "https://api.daac.asf.alaska.edu/services/search/param?dataset=NISAR&processingLevel=GCOV&intersectsWith=$POLY&start=${START}T00:00:00Z&end=${END}T23:59:59Z&output=csv&maxResults=2000"
  grep -o 'https://[^",]*\.h5' "$RAW/nisar/search.csv" | grep '_L2_PR_GCOV_' | sort -u > "$RAW/nisar/urls.txt"
  echo "NISAR: $(wc -l < "$RAW/nisar/urls.txt") files"
  # 2) download (resumable with -c); ~1-3 GB per file
  wget $EDL -c -nv -P "$RAW/nisar" -i "$RAW/nisar/urls.txt"
fi

if run dem; then
  mkdir -p "$RAW/dem"
  for T in N40_00_W006_00 N40_00_W005_00; do
    N=Copernicus_DSM_COG_10_${T}_DEM
    wget -c -nv -P "$RAW/dem" "https://copernicus-dem-30m.s3.amazonaws.com/$N/$N.tif"
  done
fi

if run soil; then
  # Cut SoilGrids 0-5 cm layers to the AOI straight from the remote VRTs (needs GDAL command-line tools)
  mkdir -p "$RAW/soil"
  for V in sand silt clay soc; do
    gdalwarp -overwrite -te $BBOX_W $BBOX_S $BBOX_E $BBOX_N -te_srs EPSG:4326 -t_srs EPSG:4326 -tr 0.0025 0.0025 \
      -r bilinear -co COMPRESS=DEFLATE \
      "/vsicurl?max_retry=3&retry_delay=1&list_dir=no&url=https://files.isric.org/soilgrids/latest/data/$V/${V}_0-5cm_mean.vrt" \
      "$RAW/soil/${V}_0-5cm.tif"
  done
fi

if run cci; then
  mkdir -p "$RAW/cci"
  BASE=https://dap.ceda.ac.uk/neodc/esacci/biomass/data/agb/maps/v5.01/geotiff/2021/
  wget -q -O "$RAW/cci/listing.html" "$BASE"
  # tiles are 10x10 degrees; keep the ones whose name starts N40W010 or N50W010 (one covers Avila)
  grep -oE '(N40W010|N50W010)_ESACCI-BIOMASS-L4-AGB-MERGED-100m-[0-9]{4}-fv[0-9.]+\.tif' "$RAW/cci/listing.html" | sort -u | \
    while read -r F; do wget -c -nv -P "$RAW/cci" "$BASE$F"; done
  echo "CCI: check with gdalinfo that one tile covers 40.4N 4.7W; delete the other."
fi

if run osm; then
  mkdir -p "$RAW/osm"
  echo "OSM: use  python steps/02_download_ancillary.py osm  (converts Overpass output to GeoJSON)"
fi

if run imerg; then
  mkdir -p "$RAW/imerg"
  wget -q -O "$RAW/imerg/cmr.json" \
    "https://cmr.earthdata.nasa.gov/search/granules.json?short_name=GPM_3IMERGHHL&version=07&temporal=2026-10-01T00:00:00Z,2026-10-08T23:59:59Z&bounding_box=$BBOX_W,$BBOX_S,$BBOX_E,$BBOX_N&page_size=2000"
  grep -oE 'https://[^"]*\.HDF5' "$RAW/imerg/cmr.json" | grep -v '\.xml' | grep -v opendap | sort -u > "$RAW/imerg/urls.txt"
  echo "IMERG: $(wc -l < "$RAW/imerg/urls.txt") files"
  wget $EDL -c -nv -P "$RAW/imerg" -i "$RAW/imerg/urls.txt"
fi
echo "wget downloads finished. Remaining Python-only sources: s2, osm, era5 (steps/02_download_ancillary.py)"
