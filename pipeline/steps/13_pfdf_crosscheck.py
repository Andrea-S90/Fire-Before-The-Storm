#!/usr/bin/env python
"""Step 13 (optional): cross-check our M1 implementation against the USGS pfdf library.

pfdf is not on PyPI; install it from the USGS GitLab:
  pip install "pfdf @ git+https://code.usgs.gov/ghsc/lhp/pfdf.git"
Then run this script. It computes M1 variables per stream segment with pfdf and reports how closely the
segment likelihoods at 24 mm/h agree with step 07. Function names follow the pfdf 3.x user guide;
if your installed version differs, check `help(pfdf.models.s17)`.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import LOG, cli, grid_from_config, load_config, path, read_raster, setup_logging, write_json  # noqa: E402


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    try:
        from pfdf import severity, watershed
        from pfdf.models import s17
        from pfdf.raster import Raster
        from pfdf.segments import Segments
    except ImportError:
        raise SystemExit("pfdf not installed (see the docstring)")
    grid = grid_from_config(cfg)
    g = lambda *p: str(path(cfg, "work", *p))  # noqa: E731
    dem = Raster.from_file(g("grid", "dem.tif"))
    sev = Raster.from_file(g("severity", "class.tif"))
    barc4 = Raster.from_array(np.nan_to_num(read_raster(g("severity", "class.tif"))).astype("int16") + 1,
                              spatial=sev)           # pfdf BARC4: 1 unburned .. 4 high
    dnbr = Raster.from_file(g("grid", "dnbr.tif")) if Path(g("grid", "dnbr.tif")).exists() else None
    kf = Raster.from_file(g("grid", "kf.tif"))
    burned = Raster.from_array(read_raster(g("severity", "class.tif")) >= 1, spatial=sev)
    modhigh = severity.mask(barc4, ["moderate", "high"])
    conditioned = watershed.condition(dem)
    flow = watershed.flow(conditioned)
    slopes = watershed.slopes(conditioned, flow)
    area_cells = cfg["hydro"]["stream_area_km2"] * 1e6 / grid.res ** 2
    acc = watershed.accumulation(flow)
    mask = acc.values >= area_cells
    segments = Segments(flow, mask, max_length=500)
    T, F, S = s17.M1.variables(segments, modhigh, slopes, dnbr, kf, omitnan=True)
    B, Ct, Cf, Cs = s17.M1.parameters(durations=15)
    p = s17.likelihood(24 / 4, B, Ct, T, Cf, F, Cs, S).ravel()
    ours = read_raster(g("hydro", "p_24mmh.tif"))
    outlets = segments.outlets()
    ov = np.array([ours[r, c] for r, c in outlets])
    ok = np.isfinite(ov) & np.isfinite(p)
    res = dict(segments=int(len(segments)), compared=int(ok.sum()),
               mean_abs_diff=float(np.mean(np.abs(ov[ok] - p[ok]))) if ok.any() else None,
               corr=float(np.corrcoef(ov[ok], p[ok])[0, 1]) if ok.sum() > 2 else None)
    write_json(path(cfg, "work", "hydro", "pfdf_crosscheck.json"), res, indent=1)
    LOG.info("pfdf cross-check: %s", res)


if __name__ == "__main__":
    main()
