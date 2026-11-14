#!/usr/bin/env python
"""Step 09: groundwater screening. Answers "which wells and springs should be tested first?"

Not a contamination forecast. Intrinsic vulnerability uses the DRASTIC factors we can map:
  D depth to water (Fan et al. water-table depth if provided, else height above nearest drainage),
  R recharge (uniform, config), A aquifer (GLHYMPS permeability if provided, else uniform),
  S soil (sand share), T topography (slope).
Score of a water point = vulnerability at the point x severity-weighted burned share of the
upslope ground within `well_radius_m`.
Outputs (data/work/groundwater/): vulnerability.tif, points.geojson (grid CRS), summary.json
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, grid_from_config, load_config, path, read_raster,  # noqa: E402
                             setup_logging, write_json, write_raster)
from ashwatch.hydro import Flow  # noqa: E402

WATER_TAGS = {("natural", "spring"), ("man_made", "water_well"), ("man_made", "water_works"),
              ("amenity", "drinking_water"), ("man_made", "water_tower"), ("man_made", "reservoir_covered"),
              ("man_made", "pumping_station")}


def rate_depth(m):      # DRASTIC depth ratings (m)
    return np.select([m < 1.5, m < 4.6, m < 9.1, m < 15.2, m < 22.9, m < 30.5], [10, 9, 7, 5, 3, 2], 1)


def rate_sand(p):       # coarser soil = faster infiltration
    return np.select([p >= 70, p >= 50, p >= 30], [9, 6, 5], 3)


def rate_slope(pct):
    return np.select([pct < 2, pct < 6, pct < 12, pct < 18], [10, 9, 5, 3], 1)


def rate_logk(lk):      # GLHYMPS log10 permeability (m2): -16 tight ... -10 very permeable
    return np.clip((lk + 16) / 6 * 9 + 1, 1, 10)


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    gc = cfg["groundwater"]
    grid = grid_from_config(cfg)
    g = lambda n: path(cfg, "work", "grid", f"{n}.tif")  # noqa: E731
    dem = read_raster(g("dem"))
    slope_t = read_raster(path(cfg, "work", "hydro", "slope_tan.tif"))

    if g("wtd").exists():
        depth = read_raster(g("wtd"))
        depth_src = "Fan et al. water-table depth"
    else:
        flow = Flow(g("dem"))
        stream = flow.area_km2() >= cfg["hydro"]["stream_area_km2"]
        depth = flow.hand(stream)
        depth_src = "height above nearest drainage (terrain proxy)"
    sand = read_raster(g("sand")) if g("sand").exists() else np.full(grid.shape, 50.0)
    A = rate_logk(read_raster(g("logk"))) if g("logk").exists() else np.full(grid.shape, gc["aquifer_rating"])
    w = gc["weights"]
    score = (w["D"] * rate_depth(np.nan_to_num(depth, nan=30)) + w["R"] * gc["recharge_rating"] + w["A"] * A
             + w["S"] * rate_sand(np.nan_to_num(sand, nan=40)) + w["T"] * rate_slope(slope_t * 100))
    vmin = sum(w.values()) * 1
    vmax = sum(w.values()) * 10
    vuln = ((score - vmin) / (vmax - vmin)).astype("float32")
    vuln[~np.isfinite(dem)] = np.nan
    write_raster(path(cfg, "work", "groundwater", "vulnerability.tif"), vuln, grid,
                 desc="Intrinsic groundwater vulnerability 0-1 (DRASTIC subset)")

    # ---------------- water points from OSM
    osm_p = path(cfg, "raw", "osm", "osm.geojson")
    feats = []
    if osm_p.exists():
        from pyproj import Transformer
        tr = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
        sev = read_raster(path(cfg, "work", "severity", "class.tif"))
        w_sev = np.array([0, 0.33, 0.66, 1.0])[np.clip(np.nan_to_num(sev).astype(int), 0, 3)]
        rad = int(gc["well_radius_m"] / grid.res)
        yy, xx = np.mgrid[-rad:rad + 1, -rad:rad + 1]
        disk = (yy ** 2 + xx ** 2) <= rad ** 2
        for f in json.loads(osm_p.read_text())["features"]:
            pr = f["properties"]
            kind = next((f"{k}={v}" for k, v in WATER_TAGS if pr.get(k) == v), None)
            if not kind:
                continue
            geom = f["geometry"]
            lon, lat = (geom["coordinates"] if geom["type"] == "Point"
                        else np.asarray(geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"]).mean(axis=0))
            x, y = tr.transform(lon, lat)
            r, c = grid.rowcol(x, y)
            if not (rad <= r < grid.height - rad and rad <= c < grid.width - rad):
                continue
            win = (slice(r - rad, r + rad + 1), slice(c - rad, c + rad + 1))
            up = disk & (dem[win] >= dem[r, c] - gc["upslope_tolerance_m"])
            share = float(w_sev[win][up].mean()) if up.any() else 0.0
            v = float(vuln[r, c]) if np.isfinite(vuln[r, c]) else None
            sc = (v or 0) * share
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]},
                          "properties": dict(name=pr.get("name"), kind=kind, osm_id=pr.get("osm_id"),
                                             vulnerability=v, burned_upslope_share=round(share, 3),
                                             score=round(sc, 3))})
    path(cfg, "work", "groundwater", "points.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": grid.crs.to_string()}},
         "features": feats}))
    summ = dict(depth_source=depth_src, aquifer_source="GLHYMPS" if g("logk").exists() else "uniform (ASSUMPTION)",
                points=len(feats), points_scored_above_0_25=sum(f["properties"]["score"] >= 0.25 for f in feats))
    write_json(path(cfg, "work", "groundwater", "summary.json"), summ, indent=1)
    LOG.info("Groundwater: %s", summ)


if __name__ == "__main__":
    main()
