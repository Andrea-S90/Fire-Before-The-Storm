# Ash Watch pipeline (runs on the HPC cluster)

Turns NISAR radar plus open data into small web files for the story site: burn severity, fuel, ash load,
debris-flow likelihood and trigger rain, erosion, groundwater screening, downwind exposure, and one risk
record per town. Heavy work runs once on the cluster; the laptop only receives `web/public/data/` (a few MB).

```
pipeline/
  config/avila.yaml        every date, path, threshold and ASSUMPTION lives here
  ashwatch/                shared code (grid, NISAR reader, hydrology + M1 model, ash Monte Carlo)
  steps/01..13_*.py        the pipeline, run in order
  scripts/                 credentials, downloads (Python and wget)
  slurm/                   batch scripts
  tests/                   synthetic end-to-end test (no internet)
```

On BlueBEAR (University of Birmingham) follow [BLUEBEAR.md](BLUEBEAR.md) instead of sections 1 to 3 below.

## 1. Set up (login node, once)

```bash
git clone https://github.com/Andrea-S90/Fire-Before-The-Storm.git && cd Fire-Before-The-Storm/pipeline
module load miniforge3            # name differs per cluster: `module avail conda`
mamba env create -f environment.yml && conda activate ashwatch
# or: python3.12 -m venv ~/venvs/ashwatch && source ~/venvs/ashwatch/bin/activate && pip install -r requirements.txt
export ASHWATCH_DATA=/scratch/$USER/ashwatch     # big files go here (~60 GB for Ávila); default is ../data
bash scripts/setup_credentials.sh               # writes ~/.netrc (Earthdata) and ~/.cdsapirc (ERA5)
bash tests/run_synthetic.sh /tmp/aw_test        # 2-5 min smoke test of the whole chain on fake data
```

Accounts (all free): [NASA Earthdata](https://urs.earthdata.nasa.gov) (approve the *Alaska Satellite Facility Data
Access* and *NASA GESDISC DATA ARCHIVE* apps in your profile) and the
[Copernicus Climate Data Store](https://cds.climate.copernicus.eu) (accept the ERA5 single-levels licence once).

## 2. Download (a node with internet: login or data-transfer node)

Python route (recommended), resumable, logs to `logs/`:

```bash
nohup bash scripts/run_downloads.sh > logs/downloads.log 2>&1 &
# or step by step:
python steps/01_download_nisar.py --dry-run     # search only: data/raw/nisar/urls.txt + manifest.csv
python steps/02_download_ancillary.py dem s2 cci soil osm era5 imerg
python steps/01_download_nisar.py               # NISAR GCOV, ~1-3 GB per file
```

Command-line route with wget (same folders; ERA5, Sentinel-2 and OSM still need the Python step):

```bash
bash scripts/download_wget.sh nisar     # ASF search API -> urls.txt -> wget with Earthdata cookies
bash scripts/download_wget.sh dem       # Copernicus DEM tiles from AWS
bash scripts/download_wget.sh soil      # SoilGrids via gdalwarp /vsicurl
bash scripts/download_wget.sh cci       # ESA CCI biomass tile
bash scripts/download_wget.sh imerg     # CMR search -> wget with Earthdata cookies
```

The raw wget call for NISAR, if you already have a URL list:

```bash
wget --load-cookies ~/.urs_cookies --save-cookies ~/.urs_cookies --keep-session-cookies \
     --auth-no-challenge=on -c -P $ASHWATCH_DATA/raw/nisar -i urls.txt
# token instead of ~/.netrc:  wget --header="Authorization: Bearer $EARTHDATA_TOKEN" -c -i urls.txt
```

**First thing after the first GCOV file lands:** `python steps/inspect_gcov.py <file.h5>`. It prints the HDF5
tree and what the reader extracts. If group or dataset names differ from what `ashwatch/nisar.py` expects
(`.../grids/frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection}`), fix them there before step 04.

Optional inputs (drop in the folder, the steps pick them up):
- `raw/effis/*.gpkg|shp|geojson` official fire perimeter (EFFIS) -> limits the burned area
- `raw/groundwater/*.nc` Fan et al. water-table depth (`downloads.wtd_url` in the config) -> replaces the terrain proxy
- `raw/groundwater/glhymps*.gpkg` GLHYMPS permeability -> replaces the uniform aquifer rating

## 3. Process (compute node, no internet needed)

```bash
mkdir -p logs && sbatch slurm/process.sbatch                        # steps 03-12, 16 cores, 64 GB
sbatch --export=ALL,STEPS="10 11 12" slurm/process.sbatch          # re-run only some steps
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

## 4. Bring the results to the laptop

```bash
# on the cluster, right after step 12: check the export against the data contract (standard library only)
python ../tools/check_data.py
# from the laptop
rsync -av user@cluster:path/to/Fire-Before-The-Storm/web/public/data/ web/public/data/
```
`layers.json` lists every overlay with its PNG and lon/lat corners (MapLibre `image` source); `towns.json` is the
record per town described in the plan doc; vectors are WGS84 GeoJSON.

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
- 401/403 on NISAR or IMERG downloads: approve the ASF / GES DISC apps in your Earthdata profile.
- ERA5 `required licences not accepted`: open the dataset page on the CDS and accept the licence.
- CCI listing fails: download the AGB GeoTIFF tile covering 40.4N 4.7W by hand into `raw/cci/`.
- No internet on compute nodes: run all downloads first (section 2), then submit section 3.
- Step 05 says no pass has dates before and after the fire: check `dates:` and `work/nisar/index.csv`.
