#!/usr/bin/env python
"""Step 11: hindcast. Did the early-October 2026 rain exceed each town's debris-flow trigger?

Reads GPM IMERG half-hourly files (mm/h) and takes the cell over each town's catchment outlet.
IMERG is a 10 km, 30-minute average, so it underestimates 15-minute peaks: treat as a lower bound.
Output: data/work/hindcast/hindcast.json
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import LOG, cli, load_config, path, read_json, setup_logging, write_json  # noqa: E402

TIME_RE = re.compile(r"(\d{8})-S(\d{6})")


def read_imerg(f, bbox, pad=0.5):
    """Precipitation (mm/h) around the AOI only: the files are global, so reading it all wastes ~25 MB each."""
    w, s, e, n = bbox
    with h5py.File(f, "r") as h:
        g = h["Grid"]
        var = "precipitation" if "precipitation" in g else "precipitationCal"
        lon, lat = g["lon"][:], g["lat"][:]
        ii = np.flatnonzero((lon >= w - pad) & (lon <= e + pad))
        jj = np.flatnonzero((lat >= s - pad) & (lat <= n + pad))
        if ii.size == 0 or jj.size == 0:
            raise SystemExit(f"{Path(f).name} does not cover the AOI")
        i0, i1, j0, j1 = ii[0], ii[-1] + 1, jj[0], jj[-1] + 1
        p = np.asarray(g[var][0, i0:i1, j0:j1], dtype="float32")          # (lon, lat)
    p[p < 0] = np.nan
    return p, lon[i0:i1], lat[j0:j1]


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    files = sorted(path(cfg, "raw", "imerg", "x").parent.glob("*.HDF5")) + sorted(path(cfg, "raw", "imerg", "x").parent.glob("*.h5"))
    if not files:
        raise SystemExit("No IMERG files in data/raw/imerg: run steps/02_download_ancillary.py imerg")
    towns = read_json(path(cfg, "work", "towns", "towns.json"))
    times, stacks = [], []
    lon = lat = None
    for f in files:
        m = TIME_RE.search(f.name)
        if not m:
            continue
        p, lon, lat = read_imerg(f, cfg["aoi"]["bbox"])
        times.append(datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"))
        stacks.append(p)
    order = np.argsort(times)
    times = [times[i] for i in order]
    stack = np.stack([stacks[i] for i in order])
    out = []
    for t in towns:
        i = int(np.argmin(np.abs(lon - t["lon"])))
        j = int(np.argmin(np.abs(lat - t["lat"])))
        series = stack[:, i, j]
        trig = t["pathways"]["debris_flow"].get("trigger_mm_h_15min")
        peak = float(np.nanmax(series)) if np.isfinite(series).any() else None
        first = None
        if trig is not None and peak is not None:
            idx = np.flatnonzero(series >= trig)
            first = times[idx[0]].isoformat() if idx.size else None
        out.append(dict(id=t["id"], name=t["name"], trigger_mm_h=trig, peak_30min_mm_h=peak,
                        total_mm=float(np.nansum(series) * 0.5), exceeded=bool(first), first_exceedance=first,
                        series=[dict(t=tt.isoformat(), mm_h=None if not np.isfinite(v) else round(float(v), 2))
                                for tt, v in zip(times, series)]))
        LOG.info("%-28s trigger %s mm/h, peak %s mm/h, exceeded %s", t["name"],
                 None if trig is None else round(trig, 1), None if peak is None else round(peak, 1), bool(first))
    write_json(path(cfg, "work", "hindcast", "hindcast.json"),
               dict(window=[cfg["dates"]["hindcast_start"], cfg["dates"]["hindcast_end"]], source="GPM IMERG Late V07",
                    note="30-min, 0.1 deg averages: a lower bound on 15-min peaks", towns=out))


if __name__ == "__main__":
    main()
