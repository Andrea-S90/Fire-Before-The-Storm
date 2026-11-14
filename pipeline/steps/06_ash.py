#!/usr/bin/env python
"""Step 06: best-estimate ash load per pixel (t/ha) = fuel consumed x ash fraction.

Fuel consumed = tree biomass x share consumed (by severity) + surface fuel x share consumed.
The ranges live in config `ash:`; step 10 runs the Monte Carlo per catchment for P10/P50/P90.
Output: data/work/ash/ash_t_ha.tif, summary.json
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.ash import ash_best_t_ha, ash_monte_carlo, pctl  # noqa: E402
from ashwatch.common import (LOG, cli, grid_from_config, load_config, path, read_raster,  # noqa: E402
                             setup_logging, write_json, write_raster)


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    grid = grid_from_config(cfg)
    agb = read_raster(path(cfg, "work", "fuel", "agb.tif"))
    sev = read_raster(path(cfg, "work", "severity", "class.tif"))
    ash = ash_best_t_ha(agb, sev, cfg["ash"])
    write_raster(path(cfg, "work", "ash", "ash_t_ha.tif"), ash, grid, desc="Best-estimate ash load (t/ha)")
    px_ha = grid.res ** 2 / 1e4
    agb_by = [float(np.nansum(agb[sev == c]) * px_ha) for c in (1, 2, 3)]
    ha_by = [float((sev == c).sum() * px_ha) for c in (1, 2, 3)]
    draws = ash_monte_carlo(agb_by, ha_by, cfg["ash"])
    summ = dict(total_ash_t_best=float(np.nansum(ash) * px_ha), total_ash_t=pctl(draws),
                burned_ha_by_class=ha_by, agb_t_by_class=agb_by)
    write_json(path(cfg, "work", "ash", "summary.json"), summ, indent=1)
    LOG.info("Total ash: best %.0f t, P10-P90 %.0f-%.0f t", summ["total_ash_t_best"],
             summ["total_ash_t"]["p10"], summ["total_ash_t"]["p90"])


if __name__ == "__main__":
    main()
