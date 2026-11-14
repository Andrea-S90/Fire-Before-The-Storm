#!/usr/bin/env python
"""Step 10: one risk record per town and reservoir -> data/work/towns/towns.json (the web data contract).

For each town the "catchment" is all land that drains through the town (snapped to the largest stream
within snap_radius_m); for a reservoir, all land draining into it. Inside that catchment:
  runoff       burned / moderate-high share, ash load (Monte Carlo P10-P90) and ash delivered (x SDR)
  debris_flow  highest M1 likelihood at 24 mm/h and lowest trigger intensity among small steep channels
  groundwater  best-scored well/spring within town_search_radius_m (screening)
  airborne     downwind exposure index at the town (indicative)
  recovery     HV change vs pre-fire over burned pixels, every NISAR date
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.ash import ash_monte_carlo, pctl  # noqa: E402
from ashwatch.common import (LOG, cli, db, grid_from_config, load_config, path, read_raster,  # noqa: E402
                             setup_logging, write_json)
from ashwatch.hydro import Flow, sdr  # noqa: E402
from ashwatch.stack import by_pass, load_index, period_mean  # noqa: E402


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def level(v, brk):
    if v is None or not np.isfinite(v):
        return "unknown"
    return "high" if v >= brk[1] else "medium" if v >= brk[0] else "low"


def worst(*lv):
    order = ["unknown", "low", "medium", "high"]
    return max(lv, key=order.index)


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    tc = cfg["towns"]
    grid = grid_from_config(cfg)
    from pyproj import Transformer
    from rasterio.features import rasterize, shapes
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    import shapely
    to_grid_crs = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True).transform

    # ---------------- targets from OSM
    osm = json.loads(path(cfg, "raw", "osm", "osm.geojson").read_text())["features"]
    named = {slug(n) for n in tc["named"]}
    targets = []
    w, s, e, n = cfg["aoi"]["bbox"]
    for f in osm:
        p, gm = f["properties"], f["geometry"]
        nm = p.get("name")
        if not nm:
            continue
        if gm["type"] == "Point" and (p.get("place") in tc["include_osm_places"] or slug(nm) in named):
            lon, lat = gm["coordinates"]
            if w <= lon <= e and s <= lat <= n:
                targets.append(dict(kind="town", name=nm, place=p.get("place"), lon=lon, lat=lat,
                                    population=int(p["population"]) if str(p.get("population", "")).isdigit() else None,
                                    named=slug(nm) in named))
        elif gm["type"] in ("Polygon", "MultiPolygon") and (p.get("water") == "reservoir" or p.get("landuse") == "reservoir"):
            geom = shape(gm)
            if slug(nm) in {slug(r) for r in tc["reservoirs"]} or geom.area > 0.0005:   # ~5 km2
                c = geom.representative_point()
                targets.append(dict(kind="reservoir", name=nm, lon=c.x, lat=c.y, geom=shapely.transform(geom, lambda xy: np.column_stack(to_grid_crs(xy[:, 0], xy[:, 1]))),
                                    named=slug(nm) in {slug(r) for r in tc["reservoirs"]}))
    seen, uniq = set(), []
    for t in targets:                       # one record per name
        if slug(t["name"]) not in seen:
            seen.add(slug(t["name"]))
            uniq.append(t)
    targets = uniq
    LOG.info("%d towns, %d reservoirs", sum(t["kind"] == "town" for t in targets), sum(t["kind"] == "reservoir" for t in targets))

    # ---------------- layers
    W = lambda *p: read_raster(path(cfg, "work", *p))  # noqa: E731
    flow = Flow(path(cfg, "work", "grid", "dem.tif"))
    area = W("hydro", "acc_km2.tif")
    sev = W("severity", "class.tif")
    agb = W("fuel", "agb.tif")
    I_ref = 24 if 24 in cfg["hydro"]["design_intensities_mm_h"] else cfg["hydro"]["design_intensities_mm_h"][0]
    p_ref = W("hydro", f"p_{I_ref}mmh.tif")
    trig = W("hydro", "trigger_mmh.tif")
    ero = W("hydro", "erosion_idx.tif")
    expo_p = path(cfg, "work", "wind", "exposure.tif")
    cg = grid.coarse(cfg["wind"]["coarse_factor"])
    expo = read_raster(expo_p) if expo_p.exists() else None
    gw_pts = []
    gw_p = path(cfg, "work", "groundwater", "points.geojson")
    if gw_p.exists():
        gw_pts = json.loads(gw_p.read_text())["features"]
    px_ha = grid.res ** 2 / 1e4
    sev_i = np.nan_to_num(sev).astype(int)

    # recovery: per-pass pre-fire HV mean (dB)
    rows = load_index(cfg)
    d = cfg["dates"]
    pre_db = {k: db(period_mean(cfg, rr, "HV", d["pre_start"], d["fire_start"])[0]) for k, rr in by_pass(rows).items()}

    rng = np.random.default_rng(cfg["ash"].get("seed", 42))
    lv = tc["levels"]
    out, polys = [], []
    for t in targets:
        if t["kind"] == "town":
            x, y = to_grid_crs(t["lon"], t["lat"])
            r0, c0 = grid.rowcol(x, y)
            r = c = None
            # snap to the largest stream nearby; widen the search until it drains >= min_catchment_km2
            for snap_m in (tc["snap_radius_m"], 2 * tc["snap_radius_m"], tc.get("max_snap_m", 1500)):
                rad = int(snap_m / grid.res)
                win = area[max(r0 - rad, 0):r0 + rad + 1, max(c0 - rad, 0):c0 + rad + 1]
                if win.size == 0 or not np.isfinite(win).any():
                    continue
                dr, dc = np.unravel_index(np.nanargmax(win), win.shape)
                r, c = max(r0 - rad, 0) + dr, max(c0 - rad, 0) + dc
                if area[r, c] >= tc.get("min_catchment_km2", 1.0):
                    break
            if r is None:
                continue
        else:
            m = rasterize([(t["geom"], 1)], out_shape=grid.shape, transform=grid.transform, fill=0, dtype="uint8") > 0
            if not m.any():
                continue
            a = np.where(m, area, -1)
            r, c = np.unravel_index(np.nanargmax(a), a.shape)
            x, y = grid.xy(r, c)
            r0, c0 = r, c
        mask = flow.catchment(r, c)
        if mask.sum() < 4:
            continue
        a_km2 = float(mask.sum() * grid.res ** 2 / 1e6)
        burned = float((sev_i[mask] >= 1).mean())
        modhigh = float((sev_i[mask] >= 2).mean())
        agb_by = [float(np.nansum(agb[mask & (sev_i == k)]) * px_ha) for k in (1, 2, 3)]
        ha_by = [float((mask & (sev_i == k)).sum() * px_ha) for k in (1, 2, 3)]
        draws = ash_monte_carlo(agb_by, ha_by, cfg["ash"], rng=rng)
        ash = pctl(draws)
        ash_del = pctl(draws * float(sdr(a_km2)))
        pm = p_ref[mask]
        tm = trig[mask]
        p_max = float(np.nanmax(pm)) if np.isfinite(pm).any() else None
        t_min = float(np.nanmin(tm)) if np.isfinite(tm).any() else None
        # groundwater: best water point near the town
        gw_best, gw_list = None, []
        for f in gw_pts:
            px, py = f["geometry"]["coordinates"]
            if np.hypot(px - x, py - y) <= cfg["groundwater"]["town_search_radius_m"]:
                gw_list.append(f["properties"])
        if gw_list:
            gw_list.sort(key=lambda q: -(q["score"] or 0))
            gw_best = gw_list[0]["score"]
        ex = None
        if expo is not None:
            er, ec = cg.rowcol(x, y)
            if 0 <= er < cg.height and 0 <= ec < cg.width and np.isfinite(expo[er, ec]):
                ex = float(expo[er, ec])
        # recovery series
        series = []
        bm = mask & (sev_i >= 2)
        if bm.sum() < 10:
            bm = mask & (sev_i >= 1)
        if bm.sum() >= 10:
            for rr_ in rows:
                if not rr_.get("HV") or rr_["key"] not in pre_db:
                    continue
                hv = db(read_raster(path(cfg, "work", "nisar", rr_["HV"])))
                dv = (hv - pre_db[rr_["key"]])[bm]
                if np.isfinite(dv).mean() > 0.5:
                    series.append(dict(date=rr_["date"], pass_id=rr_["key"], dhv_db=round(float(np.nanmedian(dv)), 2)))
        runoff_lv = worst(level(modhigh, lv["runoff_modhigh_share"]), level(ash_del["p50"], lv["runoff_ash_t"]))
        rec = dict(
            id=slug(t["name"]), name=t["name"], kind=t["kind"], lon=round(t["lon"], 5), lat=round(t["lat"], 5),
            population=t.get("population"), named_in_reports=t.get("named", False),
            catchment_km2=round(a_km2, 2), upstream_burned_pct=round(100 * burned, 1),
            upstream_modhigh_pct=round(100 * modhigh, 1),
            ash_t=ash, ash_delivered_t=ash_del, erosion_index=float(np.nansum(ero[mask])),
            pathways=dict(
                runoff=dict(level=runoff_lv, confidence="high"),
                debris_flow=dict(level=level(p_max, lv["debris_p24"]) if p_max is not None else "none",
                                 likelihood_at_24mm_h=p_max, trigger_mm_h_15min=t_min, confidence="medium"),
                groundwater=dict(level=level(gw_best, lv["groundwater_score"]) if gw_best is not None else "unknown",
                                 score=gw_best, points=gw_list[:5], confidence="screening"),
                airborne=dict(level=level(ex, lv["airborne_exposure"]), exposure_index=ex, confidence="indicative")),
            recovery=series, tests=tc["tests"])
        rec["overall"] = worst(runoff_lv, rec["pathways"]["debris_flow"]["level"] if rec["pathways"]["debris_flow"]["level"] != "none" else "low")
        out.append(rec)
        geoms = [shape(g) for g, v in shapes(mask.astype("uint8"), mask=mask, transform=grid.transform) if v == 1]
        poly = unary_union(geoms).simplify(grid.res)
        polys.append({"type": "Feature", "geometry": mapping(poly), "properties": dict(id=rec["id"], name=rec["name"])})
        LOG.info("%-28s %-9s burned %5.1f%%  ash P50 %8.0f t  p24 %s  overall %s", t["name"], t["kind"],
                 100 * burned, ash["p50"], None if p_max is None else round(p_max, 2), rec["overall"])

    order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    out.sort(key=lambda r: (order[r["overall"]], -r["ash_delivered_t"]["p50"]))
    write_json(path(cfg, "work", "towns", "towns.json"), out)
    path(cfg, "work", "towns", "catchments.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": grid.crs.to_string()}},
         "features": polys}))
    LOG.info("Wrote %d records", len(out))


if __name__ == "__main__":
    main()
