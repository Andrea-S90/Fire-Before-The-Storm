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

echo "Earthdata login. A token is the most reliable: https://urs.earthdata.nasa.gov -> Generate Token."
echo "It is valid for 60 days; run this script again to replace it."
read -rsp "Earthdata token (paste, then Enter; leave empty to use user name + password): " EDT; echo
if [ -n "${EDT}" ]; then
  ( umask 077; printf '%s\n' "${EDT}" > ~/.earthdata_token )
  echo "  saved ~/.earthdata_token"
else
  read -rp "Earthdata username (not the e-mail address; leave empty to skip): " EDU
  if [ -n "${EDU}" ]; then
    read -rsp "Earthdata password: " EDP; echo
    touch ~/.netrc && chmod 600 ~/.netrc
    # replace any earlier entry, so a mistyped password can be corrected by running this again
    grep -v "urs.earthdata.nasa.gov" ~/.netrc > ~/.netrc.tmp || true
    echo "machine urs.earthdata.nasa.gov login ${EDU} password ${EDP}" >> ~/.netrc.tmp
    chmod 600 ~/.netrc.tmp && mv ~/.netrc.tmp ~/.netrc
    rm -f ~/.earthdata_token ~/.urs_cookies
    echo "  saved ~/.netrc"
  fi
fi
touch ~/.urs_cookies

read -rsp "CDS personal access token (leave empty to skip ERA5): " CDSK; echo
if [ -n "${CDSK}" ]; then
  ( umask 077; printf "url: https://cds.climate.copernicus.eu/api\nkey: %s\n" "${CDSK}" > ~/.cdsapirc )
  echo "  saved ~/.cdsapirc"
fi
echo "Done. Check with:  python steps/01_download_nisar.py --dry-run"
