#!/usr/bin/env python
"""Step 04: read every GCOV file, cut it to the AOI and resample HH and HV onto the grid.

Averaging the 10-20 m radar pixels into 30 m cells (linear power) also reduces speckle.
Frames of the same pass and date are mosaicked. Output: data/work/nisar/<date>_<track><dir>_{HH,HV}.tif
and index.csv. Runs files in parallel ($SLURM_CPUS_PER_TASK).
"""
import csv
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from rasterio.warp import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, array_to_grid, cli, grid_from_config, load_config, n_workers,  # noqa: E402
                             path, setup_logging, write_raster)
from ashwatch.nisar import parse_name, read_gcov  # noqa: E402

POLS = {"HHHH": "HH", "HVHV": "HV"}


def _one(args):
    f, cfg = args
    grid = grid_from_config(cfg)
    try:
        g = read_gcov(f, pols=cfg["nisar"]["pols"], frequency=cfg["nisar"]["frequency"],
                      bounds=grid.bounds, bounds_crs=grid.crs)
    except Exception as ex:  # noqa: BLE001
        return f, None, f"read error: {ex}"
    if g is None or not g["pols"]:
        return f, None, "does not overlap the AOI"
    out = {}
    for p, a in g["pols"].items():
        out[POLS.get(p, p)] = array_to_grid(a, g["transform"], g["crs"], grid, Resampling.average)
    return f, out, None


def main():
    ap = cli(__doc__)
    ap.add_argument("--rebuild", action="store_true",
                    help="forget dates gridded in earlier runs (default: keep them, so raw files can be "
                         "processed and deleted pass by pass)")
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    grid = grid_from_config(cfg)
    files = sorted(path(cfg, "raw", "nisar", "x").parent.glob("*.h5"))
    info = {f: parse_name(f.name) for f in files}
    files = [f for f in files if info[f] and info[f]["prodcfg"] == cfg["nisar"]["production_config"]]
    if not files:
        raise SystemExit("No NISAR .h5 files in data/raw/nisar: run steps/01_download_nisar.py")
    LOG.info("%d GCOV files, %d workers", len(files), n_workers())

    groups = defaultdict(dict)   # (date, key) -> pol -> mosaic
    with Pool(min(n_workers(), len(files))) as pool:
        for f, res, err in pool.imap_unordered(_one, [(f, cfg) for f in files]):
            if err:
                LOG.warning("%s: %s", Path(f).name, err)
                continue
            i = info[f]
            g = groups[(i["date"], i["key"], i["crid"])]
            for p, a in res.items():
                if p in g:
                    m = np.isnan(g[p]) & ~np.isnan(a)
                    g[p][m] = a[m]
                else:
                    g[p] = a
            LOG.info("read %s", Path(f).name)

    rows = []
    for (d, key, crid), pols in sorted(groups.items()):
        rec = dict(date=d.isoformat(), key=key, track=key[:-1], dir=key[-1], crid=crid)
        for p, a in pols.items():
            fp = path(cfg, "work", "nisar", f"{d:%Y%m%d}_{key}_{p}.tif")
            write_raster(fp, a, grid, desc=f"NISAR GCOV {p} gamma0 (linear power)")
            rec[p] = fp.name
            rec[f"{p}_valid_pct"] = round(100 * float(np.isfinite(a).mean()), 1)
        rows.append(rec)
    # keep dates gridded in earlier runs whose rasters are still there (raw files may be gone by now)
    index_p = path(cfg, "work", "nisar", "index.csv")
    if index_p.exists() and not args.rebuild:
        done = {(r["date"], r["key"]) for r in rows}
        with open(index_p, newline="") as fh:
            old = [r for r in csv.DictReader(fh) if (r["date"], r["key"]) not in done
                   and all((index_p.parent / r[p]).exists() for p in ("HH", "HV") if r.get(p))]
        if old:
            LOG.info("Keeping %d dates x passes from earlier runs", len(old))
        rows = sorted(rows + old, key=lambda r: (r["date"], r["key"], r["crid"]))
    with open(index_p, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=["date", "key", "track", "dir", "crid", "HH", "HV",
                                            "HH_valid_pct", "HV_valid_pct"])
        wr.writeheader()
        wr.writerows(rows)
    LOG.info("Stack: %d dates x passes -> data/work/nisar/index.csv", len(rows))


if __name__ == "__main__":
    main()
