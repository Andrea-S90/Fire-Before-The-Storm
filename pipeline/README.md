# Ash Watch pipeline

Turns NISAR radar plus open data into small web files for the story site: burn severity, fuel, ash load,
debris-flow likelihood and trigger rain, erosion, groundwater screening, downwind exposure, and one risk
record per town. It runs on one Linux or macOS machine (on Windows, use WSL). The site only needs the
export in `web/public/data/`, which is already committed, so you do not have to run the pipeline to see the site.

```
pipeline/
  config/avila.yaml        every date, path, threshold and ASSUMPTION lives here
  ashwatch/                shared code (grid, NISAR reader, hydrology + M1 model, ash Monte Carlo)
  steps/01..13_*.py        the pipeline, run in order
  scripts/                 credentials, downloads, run script
  tests/                   synthetic end-to-end test (no internet)
```

## What you need

- **Disk.** The NISAR files for the Ávila case are about 1.5 to 2.1 GB each and there are 40 or more of them
  (about 70 to 80 GB, growing as new acquisitions are published). Either keep 100 GB free, or use the
  pass-by-pass route below, which needs about 30 GB because it deletes each pass's raw files once they are
  gridded. Everything else is under 1 GB.
- **Memory and cores.** Our run used 16 cores and 64 GB and took well under an hour for steps 03 to 12. We did
  not measure the minimum; set `ASHWATCH_WORKERS` to a small number if memory is tight.
- **Accounts (free).** [NASA Earthdata](https://urs.earthdata.nasa.gov): approve the *Alaska Satellite Facility
  Data Access* and *NASA GESDISC DATA ARCHIVE* apps in your profile and generate a token.
  [Copernicus Climate Data Store](https://cds.climate.copernicus.eu): copy your personal access token and
  accept the ERA5 single-levels licence once.
- **Python 3.11 or 3.12.**

## 1. Set up

```bash
git clone https://github.com/Andrea-S90/Fire-Before-The-Storm.git && cd Fire-Before-The-Storm/pipeline
python3 -m venv ~/venvs/ashwatch && source ~/venvs/ashwatch/bin/activate && pip install -r requirements.txt
# or with conda/mamba:  mamba env create -f environment.yml && conda activate ashwatch
export ASHWATCH_DATA=/path/with/space/ashwatch_data   # raw downloads + intermediate rasters; default is ../data
bash tests/run_synthetic.sh /tmp/aw_test              # 2-5 min smoke test of the whole chain on fake data
bash scripts/setup_credentials.sh                     # asks for the two tokens, writes ~/.earthdata_token and ~/.cdsapirc
```

The smoke test must end with `OK: web files in ...` and list 9 PNG files before you download anything.

## 2. Download

Small first test (a few GB), to check the logins and the NISAR file layout:

```bash
python steps/01_download_nisar.py --dry-run     # search only: writes raw/nisar/urls.txt + manifest.csv
python steps/02_download_ancillary.py dem s2 cci soil osm imerg era5
python steps/01_download_nisar.py --max-files 2
python steps/inspect_gcov.py "$(ls $ASHWATCH_DATA/raw/nisar/*_PR_GCOV_*.h5 | head -1)"
```

`inspect_gcov.py` prints the HDF5 tree and what the reader extracts: `HHHH` and `HVHV` with medians between
about -25 and -5 dB. If group or dataset names differ from what `ashwatch/nisar.py` expects
(`.../grids/frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection}`), fix them there before step 04.
ERA5 requests wait in a queue at the CDS, sometimes for hours; nothing else depends on them until step 08.

Then the rest, one of two ways. Both resume where they stopped if you run them again.

**With 100 GB free: everything at once.**

```bash
mkdir -p logs && nohup bash scripts/run_downloads.sh > logs/downloads.log 2>&1 &
```

**With less disk: pass by pass.** Downloads one satellite pass (15 to 20 GB), grids it (step 04), checks
that every date is in the stack, deletes that pass's raw files, and moves to the next pass. If a date is
missing it stops and keeps the raw files.

```bash
python steps/02_download_ancillary.py dem s2 cci soil osm imerg era5
bash scripts/nisar_in_batches.sh                      # or: PASSES="087A 095D" bash scripts/nisar_in_batches.sh
```

There is also a wget route for the plain file downloads (`scripts/download_wget.sh`); ERA5, Sentinel-2 and
OSM still need the Python step.

Optional inputs (drop in the folder, the steps pick them up):
- `raw/effis/*.gpkg|shp|geojson` official fire perimeter (EFFIS) -> limits the burned area
- `raw/groundwater/*.nc` Fan et al. water-table depth (`downloads.wtd_url` in the config) -> replaces the terrain proxy
- `raw/groundwater/glhymps*.gpkg` GLHYMPS permeability -> replaces the uniform aquifer rating

## 3. Process

```bash
bash scripts/run_pipeline.sh                                   # steps 03-12
bash scripts/run_pipeline.sh 03 05 06 07 08 09 10 11 12        # after the pass-by-pass route (04 is already done)
bash scripts/run_pipeline.sh 10 11 12                          # re-run only some steps
```

| Step | What it does | Main outputs (`$ASHWATCH_DATA/work/`) |
| --- | --- | --- |
| 03 | DEM, Sentinel-2 dNBR, CCI biomass, soil and erodibility onto one 30 m grid (EPSG:25830) | `grid/*.tif` |
| 04 | Every GCOV file cut to the AOI, HH/HV averaged to 30 m, frames mosaicked | `nisar/*_HV.tif`, `index.csv` |
| 05 | Fuel: HV -> biomass fitted on CCI. Severity: burned where the per-pass HV drop and Sentinel-2 dNBR agree; class from dNBR, random forest on radar where dNBR is missing | `fuel/agb.tif`, `severity/class.tif`, `metrics.json` |
| 06 | Ash load per pixel (best estimate) and total with Monte Carlo range | `ash/ash_t_ha.tif` |
| 07 | Flow routing, Staley M1 likelihood + trigger rain, erosion index, ash transport, streams | `hydro/*.tif`, `streams.geojson` |
| 08 | ERA5 wind rose during the fire, downwind exposure, dry windy days | `wind/rose.json`, `exposure.tif` |
| 09 | Groundwater vulnerability and scores for OSM wells/springs (screening) | `groundwater/*` |
| 10 | One record per town/reservoir: all pathways, ash P10-P90, recovery series | `towns/towns.json` |
| 11 | Hindcast: early-October IMERG rain vs each town's trigger | `hindcast/hindcast.json` |
| 12 | Web export: PNG overlays + GeoJSON + JSON (the data contract) | `web/public/data/` |
| 13 | Optional: compare our M1 with the USGS pfdf library | `hydro/pfdf_crosscheck.json` |

## 4. Check and use the results

```bash
python ../tools/check_data.py        # checks the export against the data contract (standard library only)
cd ../web && npm install && npm run dev
```

Step 12 writes straight into `web/public/data/`. `layers.json` lists every overlay with its PNG and lon/lat
corners (MapLibre `image` source); `towns.json` is the record per town described in `docs/DATA_CONTRACT.md`;
vectors are WGS84 GeoJSON.

## Methods in one paragraph each

- **Radar change** is computed per pass (same track and direction) so the viewing geometry is identical, then
  averaged across passes. Pre-fire = Jun 17 to Jul 21, post-fire = Aug 7 to Sep 25 (before autumn rain, so soil
  moisture does not mimic burn). HV tracks woody biomass; HH responds to soil moisture and roughness.
- **Burned area**: a pixel is burned only if HV fell by at least `severity.burn_dhv_db` (1 dB) relative to the
  scene median and Sentinel-2 dNBR reaches 100, in patches of 5 ha or more. dNBR alone flags summer drying and
  harvest; radar alone flags moisture and swath-edge effects; requiring both removes most of each. Under cloud
  the radar decides alone. `metrics.json` reports how often the two agree. An EFFIS perimeter in `raw/effis/`
  limits the burn further.
- **Fuel**: `ln(AGB) = a + b * HV_dB`, fitted on ESA CCI pixels between 5 and 150 Mg/ha. L-band HV saturates
  around 100 Mg/ha, so those pixels are flagged and the ash there is a lower bound.
- **Debris flow**: Staley et al. (2017) M1, 15-min parameters from the config, implemented directly
  (`ashwatch/hydro.py`); applied to catchments of 0.025-8 km2. Calibrated in the western US: present as a ranking.
- **Ash**: fuel consumed x ash fraction, every fraction a range in the config (ASSUMPTION), Monte Carlo per catchment.
- **Groundwater**: DRASTIC subset x burned share upslope of each water point. A "test first" list, not a forecast.
- **Wind**: speed-weighted hours per direction during the fire, decaying with distance. Indicative only.

## Troubleshooting

- `No Earthdata credentials`: run `scripts/setup_credentials.sh` or `export EARTHDATA_TOKEN=...`.
- `Invalid user credentials`: the Earthdata user name or password is wrong; run `scripts/setup_credentials.sh`
  again and paste a token instead.
- 401/403 on NISAR or IMERG downloads: approve the ASF / GES DISC apps in your Earthdata profile.
- ERA5 `required licences not accepted`: open the dataset page on the CDS and accept the licence.
- CCI listing fails: download the AGB GeoTIFF tile covering 40.4N 4.7W by hand into `raw/cci/`.
- `Missing/incomplete configuration file: ~/.cdsapirc`: the CDS token was skipped; run the setup script again.
- OSM download fails: the Overpass server is sometimes busy; run `python steps/02_download_ancillary.py osm` again.
- Out of disk during the NISAR download: switch to `scripts/nisar_in_batches.sh`; files already there are kept.
- Step 05 says no pass has dates before and after the fire: check `dates:` and `work/nisar/index.csv`.
