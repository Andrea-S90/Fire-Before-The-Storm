# Data contract: `web/public/data/`

The only interface between the pipeline (Masha) and the site (Andrea). Step 12 writes these files; the site
only reads them. `python tools/check_data.py` checks every rule on this page and runs in CI and before each
deploy.

**Changing the contract.** Adding a field or a file is always safe. Renaming or removing one needs, in the
same pull request: this page, `tools/check_data.py`, and the site code that reads it.

This page describes what step 12 exports today. Where it differs from the build plan, the export wins.

## Files

| File | Written by | What it is |
| --- | --- | --- |
| `meta.json` | step 12 | Export time, config name, AOI, dates, per-step metrics, sources |
| `layers.json` + `img/<id>.png` | step 12 | Raster overlays in Web Mercator with their corners |
| `towns.json` | step 10 | One risk record per town or reservoir |
| `towns.geojson` | step 12 | Town points with the levels, for map styling |
| `catchments.geojson` | step 10 | One polygon per town: the land draining through it |
| `streams.geojson` | step 07 | Stream segments with debris-flow values |
| `water_points.geojson` | step 09 | OSM wells, springs and water works with a screening score |
| `burned_area.geojson` | step 12 | Burn outline from the severity map |
| `hindcast.json` | step 11 | Early-October rain against each town's trigger |
| `wind_rose.json` | step 08 | Wind during the fire, by direction and speed |

All vectors are WGS84 lon/lat. Budget: under 100 MB in total.

## `meta.json`

`generated` (ISO time, UTC), `config`, `aoi_bbox` `[lon_min, lat_min, lon_max, lat_max]`, `dates` (ISO
strings), `sources` (list of credits), and one block of metrics per step: `severity`, `ash`, `hydro`, `wind`,
`groundwater`. The site shows `generated` in its footer, so anyone can see which export is live.

## `layers.json`

A list. Each layer: `id`, `title`, `url` (relative, `img/<id>.png`), `units`, `legend`, and `coordinates`:
four `[lon, lat]` corners in the order top-left, top-right, bottom-right, bottom-left (a MapLibre image
source). Current ids: `hv_pre`, `hv_post`, `dhv`, `severity`, `biomass`, `ash`, `erosion`, `gw_vuln`,
`wind_exposure`. `legend` is `{cmap, min, max}` or, for classes, `{classes, colors}`.

## `towns.json`

A list, sorted by overall level then by ash delivered. The values below are illustrative.

```json
{"id": "piedralaves", "name": "Piedralaves", "kind": "town | reservoir",
 "lon": -4.69, "lat": 40.31, "population": 2159, "named_in_reports": true,
 "catchment_km2": 9.69, "upstream_burned_pct": 52.2, "upstream_modhigh_pct": 40.1,
 "ash_t": {"p10": 0, "p50": 0, "p90": 0},
 "ash_delivered_t": {"p10": 0, "p50": 0, "p90": 0},
 "erosion_index": 0,
 "pathways": {
   "runoff":      {"level": "high", "confidence": "high"},
   "debris_flow": {"level": "high", "likelihood_at_24mm_h": 0.7, "trigger_mm_h_15min": 14.7, "confidence": "medium"},
   "groundwater": {"level": "medium", "score": 0.4, "points": [], "confidence": "screening"},
   "airborne":    {"level": "medium", "exposure_index": 0.3, "confidence": "indicative"}},
 "recovery": [{"date": "2026-08-19", "pass_id": "087A", "dhv_db": -0.31}],
 "tests": ["turbidity", "manganese"],
 "overall": "high"}
```

- `id` is a lowercase slug, unique, and the join key for `towns.geojson`, `catchments.geojson` and
  `hindcast.json`.
- Levels are `high`, `medium`, `low`, `unknown` (and `none` for debris flow where the model does not apply).
- `population` may be null. `trigger_mm_h_15min` is a rain intensity in mm/h sustained for 15 minutes.
- `recovery[].dhv_db` is HV change against the pre-fire mean of the same pass, over burned pixels.

Differences from the build plan: the trigger sits under `debris_flow` (runoff has no trigger yet), airborne
has `exposure_index` instead of `downwind_hours`, and recovery has `dhv_db` instead of `hv_db`.

## Vectors

- `towns.geojson` properties: `id`, `name`, `kind`, `overall`, `runoff`, `debris_flow`, `groundwater`, `airborne`.
- `catchments.geojson` properties: `id`, `name`.
- `streams.geojson` properties: `id`, `area_km2`, `burned_share`, `p24` (likelihood at 24 mm/h),
  `trigger_mmh`, `ash_up_t`, `T`, `F`, `S` (the M1 model terms). `p24` and `trigger_mmh` are null outside the
  model's catchment size range.
- `water_points.geojson` properties: `name`, `kind`, `osm_id`, `vulnerability`, `burned_upslope_share`, `score`.

## `hindcast.json`

`window`, `source`, `note`, and `towns`: a list of `{id, name, trigger_mm_h, peak_30min_mm_h, total_mm,
exceeded, first_exceedance, series: [{t, mm_h}]}` with one half-hourly value per step of the window.

## `wind_rose.json`

`window`, `speed_bins_m_s`, and `sectors`: a list of `{direction_from_deg, hours, by_speed}`.
