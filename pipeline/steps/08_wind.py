#!/usr/bin/env python
"""Step 08: wind during the fire (ERA5) -> wind rose, downwind ash-exposure index, dry windy days.

Exposure index (indicative, not measured deposition): for every coarse cell, sum over wind sectors of
  (speed-weighted hours blowing towards that cell's bearing from a burned source) x exp(-distance / decay),
averaged over burned source points weighted by severity, then scaled to 0-1.
Outputs (data/work/wind/): rose.json, exposure.tif (coarse grid), summary.json
"""
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, grid_from_config, load_config, path, read_raster,  # noqa: E402
                             setup_logging, write_json, write_raster)


def load_era5(cfg):
    files = sorted(path(cfg, "raw", "era5", "x").parent.glob("*.nc"))
    if not files:
        raise SystemExit("No ERA5 files in data/raw/era5: run steps/02_download_ancillary.py era5")
    parts = [xr.open_dataset(f) for f in files]
    tname = "valid_time" if "valid_time" in parts[0].coords else "time"
    ds = xr.concat(parts, dim=tname) if len(parts) > 1 else parts[0]
    lat = "latitude" if "latitude" in ds.coords else "lat"
    lon = "longitude" if "longitude" in ds.coords else "lon"
    cx, cy = cfg["aoi"]["center"]
    p = ds.sel({lat: cy, lon: cx}, method="nearest")
    for extra in ("expver", "number"):
        if extra in p.dims:
            p = p.isel({extra: 0})
    t = p[tname].values.astype("datetime64[s]").astype(datetime)
    u, v = p["u10"].values.astype(float), p["v10"].values.astype(float)
    tp = p["tp"].values.astype(float) * 1000.0 if "tp" in p else np.zeros_like(u)   # m -> mm
    order = np.argsort(t)
    return np.asarray(t)[order], u[order], v[order], tp[order]


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    wc = cfg["wind"]
    d = cfg["dates"]
    grid = grid_from_config(cfg)
    t, u, v, tp = load_era5(cfg)
    speed = np.hypot(u, v)
    wdir_from = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0
    fire = (t >= datetime.combine(d["fire_start"], time())) & (t < datetime.combine(d["fire_end"] + timedelta(days=1), time()))
    if not fire.any():
        raise SystemExit("ERA5 does not cover the fire window")

    nsec = wc["sector_count"]
    width = 360 / nsec
    sec = (((wdir_from + width / 2) % 360) // width).astype(int)
    bins = wc["speed_bins_m_s"]
    rose = []
    for s in range(nsec):
        m = fire & (sec == s)
        counts = np.histogram(speed[m], bins=bins)[0]
        rose.append(dict(direction_from_deg=s * width, hours=int(m.sum()), by_speed=counts.tolist()))
    write_json(path(cfg, "work", "wind", "rose.json"),
               dict(window=[d["fire_start"], d["fire_end"]], speed_bins_m_s=bins, sectors=rose,
                    note="ERA5 hourly 10 m wind at the AOI centre; direction the wind blows FROM"))

    # ---------------- downwind exposure
    sev = read_raster(path(cfg, "work", "severity", "class.tif"))
    w_sev = np.array([0, 0.33, 0.66, 1.0])[np.clip(np.nan_to_num(sev).astype(int), 0, 3)]
    src_idx = np.flatnonzero(w_sev > 0)
    if src_idx.size == 0:
        raise SystemExit("No burned pixels found; run step 05 first")
    rng = np.random.default_rng(3)
    src_idx = rng.choice(src_idx, size=min(wc["max_sources"], src_idx.size), replace=False)
    sr, scc = np.unravel_index(src_idx, grid.shape)
    sx, sy = grid.xy(sr, scc)
    sw = w_sev.ravel()[src_idx]
    cg = grid.coarse(wc["coarse_factor"])
    rr, cc = np.mgrid[0:cg.height, 0:cg.width]
    gx, gy = cg.xy(rr.ravel(), cc.ravel())
    # speed-weighted hours per "blowing towards" sector
    to_sec = (sec + nsec // 2) % nsec
    W = np.array([speed[fire & (to_sec == s)].sum() for s in range(nsec)])
    W = W / W.sum()
    expo = np.zeros(gx.size)
    L = wc["decay_km"] * 1000.0
    for k in range(0, sx.size, 100):
        dx = gx[None, :] - sx[k:k + 100, None]
        dy = gy[None, :] - sy[k:k + 100, None]
        dist = np.hypot(dx, dy)
        bearing = (np.degrees(np.arctan2(dx, dy)) % 360.0)          # from source to cell, clockwise from north
        bsec = (((bearing + width / 2) % 360) // width).astype(int)
        expo += (sw[k:k + 100, None] * W[bsec] * np.exp(-dist / L)).sum(axis=0)
    expo = expo / max(expo.max(), 1e-12)
    write_raster(path(cfg, "work", "wind", "exposure.tif"), expo.reshape(cg.shape).astype("float32"), cg,
                 desc="Downwind ash exposure index 0-1 (indicative)")

    # ---------------- dry windy days after the fire, before the first real rain
    after = t >= datetime.combine(d["fire_end"] + timedelta(days=1), time())
    days = sorted({x.date() for x in t[after]})
    windy, first_rain = 0, None
    for day in days:
        m = np.array([x.date() == day for x in t])
        if tp[m].sum() >= wc["first_rain_mm_day"]:
            first_rain = day
            break
        if speed[m].max() >= wc["windy_day_m_s"]:
            windy += 1
    summ = dict(fire_hours=int(fire.sum()), mean_speed_m_s=float(speed[fire].mean()),
                dominant_from_deg=float(rose[int(np.argmax([r["hours"] for r in rose]))]["direction_from_deg"]),
                dry_windy_days_before_first_rain=windy, first_rain_day=first_rain)
    write_json(path(cfg, "work", "wind", "summary.json"), summ, indent=1)
    LOG.info("Wind: %s", summ)


if __name__ == "__main__":
    main()
