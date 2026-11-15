#!/usr/bin/env python
"""Step 07: flow routing, debris-flow likelihood (Staley M1), trigger rain, erosion and ash transport.

Outputs (data/work/hydro/):
  fdir.tif, acc_km2.tif, slope_tan.tif
  m1_T.tif, m1_F.tif, m1_S.tif, p_<I>mmh.tif (likelihood at design 15-min intensities),
  trigger_mmh.tif (15-min intensity giving 50% likelihood; only where M1 applies)
  erosion_idx.tif (relative RUSLE: K * LS * C), ash_up_t.tif (ash upstream, t), ash_delivered_t.tif
  burned_up_share.tif, modhigh_up_share.tif
  streams.geojson (grid CRS; one feature per segment with values at its downstream end)
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, grid_from_config, load_config, path, read_raster,  # noqa: E402
                             require, setup_logging, write_json, write_raster)
from ashwatch.hydro import (Flow, m1_likelihood, m1_threshold_mm, m1_variables, rusle_ls,  # noqa: E402
                            sdr, slope_tan)


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    hc = cfg["hydro"]
    grid = grid_from_config(cfg)
    W = lambda name, a, **kw: write_raster(path(cfg, "work", "hydro", f"{name}.tif"), a, grid, **kw)  # noqa: E731

    dem_p = require(path(cfg, "work", "grid", "dem.tif"), "run steps/03_prepare_grid.py")
    LOG.info("Conditioning DEM and routing flow (pysheds)...")
    flow = Flow(dem_p)
    dem = np.asarray(flow.dem, dtype="float32")
    area = flow.area_km2().astype("float32")
    slope_t = slope_tan(dem, grid.res)
    W("fdir", np.asarray(flow.fdir).astype("int16"), nodata=-1, dtype="int16")
    W("acc_km2", area)
    W("slope_tan", slope_t)

    sev = read_raster(path(cfg, "work", "severity", "class.tif"))
    burned = np.nan_to_num(sev) >= 1
    modhigh = np.nan_to_num(sev) >= 2
    dnbr_p = path(cfg, "work", "grid", "dnbr.tif")
    if dnbr_p.exists():
        dnbr = read_raster(dnbr_p)
        # fill smoke/cloud gaps with the class-median dNBR so F stays defined
        fill = np.array([50, 185, 465, 800], "float32")
        gap = ~np.isfinite(dnbr) & np.isfinite(sev)
        dnbr[gap] = fill[np.clip(np.nan_to_num(sev[gap]).astype(int), 0, 3)]
    else:
        LOG.warning("No dNBR: fire variable F from severity class midpoints (ASSUMPTION)")
        dnbr = np.array([50, 185, 465, 800], "float32")[np.clip(np.nan_to_num(sev).astype(int), 0, 3)]
    # F is the fire's dNBR: zero outside the burn. Raw dNBR is also high over drying fields and is noise over
    # water (a ratio of two near-zero reflectances), which made unburned catchments look dangerous.
    dnbr = np.where(burned, np.clip(np.nan_to_num(dnbr), 0, 1500), 0).astype("float32")
    kf = read_raster(path(cfg, "work", "grid", "kf.tif"))
    kf = np.where(np.isfinite(kf), kf, np.nanmedian(kf))

    LOG.info("M1 variables...")
    T, F, S = m1_variables(flow, modhigh, slope_t, dnbr, kf, hc["steep_slope_deg"])
    params = hc["m1_15min"]
    domain = (area >= hc["m1_min_area_km2"]) & (area <= hc["m1_max_area_km2"])
    stream = area >= hc["stream_area_km2"]
    for name, a in (("m1_T", T), ("m1_F", F), ("m1_S", S)):
        W(name, a)
    ps = {}
    for I in hc["design_intensities_mm_h"]:
        p = m1_likelihood(T, F, S, I / 4.0, params).astype("float32")   # 15-min accumulation = I / 4
        p[~domain] = np.nan
        ps[I] = p
        W(f"p_{I}mmh", p)
    trig = (m1_threshold_mm(T, F, S, params) * 4.0).astype("float32")  # back to mm/h
    trig[~domain | ~np.isfinite(trig) | (trig <= 0)] = np.nan
    W("trigger_mmh", trig)

    LOG.info("Erosion index and ash transport...")
    c_fac = np.array(hc["rusle_c"], "float32")[np.clip(np.nan_to_num(sev).astype(int), 0, 3)]
    ero = kf * rusle_ls(np.asarray(flow.acc), slope_t, grid.res) * c_fac
    W("erosion_idx", ero.astype("float32"))
    ash = read_raster(path(cfg, "work", "ash", "ash_t_ha.tif"))
    ash_t = np.nan_to_num(ash) * grid.res ** 2 / 1e4
    ash_up = flow.upslope_sum(ash_t).astype("float32")
    W("ash_up_t", ash_up)
    W("ash_delivered_t", (ash_up * sdr(area)).astype("float32"))
    W("burned_up_share", flow.upslope_mean(burned.astype("float64")).astype("float32"))
    W("modhigh_up_share", flow.upslope_mean(modhigh.astype("float64")).astype("float32"))

    LOG.info("Extracting stream network...")
    net = flow.river_network(stream)
    bshare = read_raster(path(cfg, "work", "hydro", "burned_up_share.tif"))
    feats = []
    I_ref = 24 if 24 in ps else hc["design_intensities_mm_h"][0]
    for i, ft in enumerate(net["features"]):
        coords = ft["geometry"]["coordinates"]
        if len(coords) < 2:
            continue
        x, y = coords[-1]
        r, c = grid.rowcol(x, y)
        r, c = int(np.clip(r, 0, grid.height - 1)), int(np.clip(c, 0, grid.width - 1))
        val = lambda a: (None if not np.isfinite(a[r, c]) else round(float(a[r, c]), 4))  # noqa: E731
        props = dict(id=i, area_km2=val(area), burned_share=val(bshare), p24=val(ps[I_ref]),
                     trigger_mmh=val(trig), ash_up_t=val(ash_up), T=val(T), F=val(F), S=val(S))
        feats.append({"type": "Feature", "geometry": ft["geometry"], "properties": props})
    gj = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": grid.crs.to_string()}},
          "features": feats}
    path(cfg, "work", "hydro", "streams.geojson").write_text(json.dumps(gj))
    summ = dict(segments=len(feats), m1_domain_km2=float(domain.sum() * flow.cell_km2),
                p24_max=float(np.nanmax(ps[I_ref])) if np.isfinite(ps[I_ref]).any() else None,
                trigger_mmh_min=float(np.nanmin(trig)) if np.isfinite(trig).any() else None)
    write_json(path(cfg, "work", "hydro", "summary.json"), summ, indent=1)
    LOG.info("Streams: %d segments; %s", len(feats), summ)


if __name__ == "__main__":
    main()
