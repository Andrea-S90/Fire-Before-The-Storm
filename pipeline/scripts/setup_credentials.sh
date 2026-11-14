#!/usr/bin/env bash
# One-time credential setup on the cluster (run on the login node). Never commit these files.
#
# 1) NASA Earthdata login (NISAR via ASF, GPM IMERG via GES DISC)
#    - Account: https://urs.earthdata.nasa.gov  (free)
#    - In your Earthdata profile -> Applications -> Authorized Apps, approve:
#        "Alaska Satellite Facility Data Access" and "NASA GESDISC DATA ARCHIVE"
# 2) Copernicus Climate Data Store (ERA5)
#    - Account: https://cds.climate.copernicus.eu  -> your profile -> Personal Access Token
#    - Open the ERA5 single-levels dataset page once and accept the licence (Download tab, bottom)
set -euo pipefail

read -rp "Earthdata username: " EDU
read -rsp "Earthdata password: " EDP; echo
touch ~/.netrc && chmod 600 ~/.netrc
grep -q "urs.earthdata.nasa.gov" ~/.netrc 2>/dev/null || \
  echo "machine urs.earthdata.nasa.gov login ${EDU} password ${EDP}" >> ~/.netrc
touch ~/.urs_cookies

read -rp "CDS personal access token (leave empty to skip ERA5): " CDSK
if [ -n "${CDSK}" ]; then
  printf "url: https://cds.climate.copernicus.eu/api\nkey: %s\n" "${CDSK}" > ~/.cdsapirc
  chmod 600 ~/.cdsapirc
fi
echo "Done. ~/.netrc and ~/.cdsapirc are set (chmod 600)."
echo "Optional: export EARTHDATA_TOKEN=<token from urs.earthdata.nasa.gov -> Generate Token> for token auth."
