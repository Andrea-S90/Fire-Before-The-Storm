#!/usr/bin/env python
"""Step 05: pre-fire fuel (biomass) and burn severity from NISAR, checked against Sentinel-2.

Fuel:     pre-fire HV (dB) -> AGB with a power law fitted on ESA CCI pixels (log AGB = a + b * HV_dB).
Severity: per-pass HV and HH change (post-fire vs pre-fire mean). A random forest learns Sentinel-2
          dNBR classes from the radar features on cloud/smoke-free pixels, then maps every pixel.
          Without dNBR, fixed HV-change breaks from the config are used.
Outputs (data/work/): fuel/agb.tif, fuel/saturated.tif, severity/{dhv_db,dhh_db,hv_pre_db,hv_post_db,
          class,prob}.tif, severity/metrics.json
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, grid_from_config, load_config, n_workers, path,  # noqa: E402
                             read_raster, setup_logging, write_json, write_raster)
from ashwatch.stack import change_db, load_index  # noqa: E402

CLASSES = ["unburned", "low", "moderate", "high"]


def classify_dnbr(dnbr, breaks):
    c = np.digitize(dnbr, breaks).astype("float32")
    c[~np.isfinite(dnbr)] = np.nan
    return c


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    grid = grid_from_config(cfg)
    d = cfg["dates"]
    rows = load_index(cfg)
    pre, post = (d["pre_start"], d["fire_start"]), (d["post_start"], d["post_end"])
    metrics = dict(pre_window=pre, post_window=post)

    dhv, hv_pre, hv_post, used = change_db(cfg, rows, "HV", pre, post)
    dhh, hh_pre, hh_post, _ = change_db(cfg, rows, "HH", pre, post)
    metrics["passes"] = used
    for name, a in (("dhv_db", dhv), ("dhh_db", dhh), ("hv_pre_db", hv_pre), ("hv_post_db", hv_post),
                    ("hh_pre_db", hh_pre), ("hh_post_db", hh_post)):
        write_raster(path(cfg, "work", "severity", f"{name}.tif"), a, grid)
    LOG.info("HV change: median %.2f dB, 5th pct %.2f dB", np.nanmedian(dhv), np.nanpercentile(dhv, 5))

    # ---------------- fuel
    fc = cfg["fuel"]
    cci_p = path(cfg, "work", "grid", "agb_cci.tif")
    if cci_p.exists():
        from sklearn.linear_model import HuberRegressor
        cci = read_raster(cci_p)
        ok = np.isfinite(cci) & np.isfinite(hv_pre) & (cci >= fc["fit_agb_min"]) & (cci <= fc["fit_agb_max"])
        idx = np.flatnonzero(ok)
        rng = np.random.default_rng(0)
        idx = rng.choice(idx, size=min(200_000, idx.size), replace=False)
        X, y = hv_pre.ravel()[idx, None], np.log(cci.ravel()[idx])
        model = HuberRegressor(max_iter=500).fit(X, y)
        a, b = float(model.intercept_), float(model.coef_[0])
        agb = np.exp(a + b * hv_pre)
        r2 = float(np.corrcoef(np.exp(model.predict(X)), np.exp(y))[0, 1] ** 2)
        metrics["fuel"] = dict(method="HV power law fitted on ESA CCI", a=a, b=b, r2=r2, n=int(idx.size))
        LOG.info("Fuel model: ln(AGB) = %.3f + %.3f * HV_dB  (R2 = %.2f, n = %d)", a, b, r2, idx.size)
    else:
        lo, hi = fc["fallback_hv_db_range"]
        agb = np.clip((hv_pre - lo) / (hi - lo), 0, 1) * fc["fallback_max_agb"]
        metrics["fuel"] = dict(method="fallback linear HV scaling (ASSUMPTION, no CCI)")
        LOG.warning("No CCI: fallback fuel scaling")
    agb = np.clip(agb, 0, fc["max_agb"]).astype("float32")
    write_raster(path(cfg, "work", "fuel", "agb.tif"), agb, grid, desc="Pre-fire AGB from NISAR HV (Mg/ha)")
    sat = (agb > fc["saturation_mg_ha"]).astype("uint8")
    write_raster(path(cfg, "work", "fuel", "saturated.tif"), sat, grid, nodata=255, dtype="uint8")
    metrics["fuel"]["saturated_share"] = float(sat[np.isfinite(hv_pre)].mean())

    # ---------------- severity
    feats = np.stack([dhv, dhh, dhv - dhh, hv_pre, hh_pre]).reshape(5, -1).T
    valid = np.all(np.isfinite(feats), axis=1)
    sev = np.full(grid.shape, np.nan, "float32")
    prob = np.full(grid.shape, np.nan, "float32")
    dnbr_p = path(cfg, "work", "grid", "dnbr.tif")
    if dnbr_p.exists():
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import cohen_kappa_score, confusion_matrix
        labels = classify_dnbr(read_raster(dnbr_p), cfg["severity"]["dnbr_breaks"]).ravel()
        train = np.flatnonzero(valid & np.isfinite(labels))
        rng = np.random.default_rng(1)
        # balance: up to rf_samples / 4 per class
        per = cfg["severity"]["rf_samples"] // 4
        pick = np.concatenate([rng.choice(train[labels[train] == c], size=min(per, int((labels[train] == c).sum())),
                                          replace=False) for c in range(4) if (labels[train] == c).any()])
        rng.shuffle(pick)
        cut = int(0.7 * pick.size)
        tr, te = pick[:cut], pick[cut:]
        rf = RandomForestClassifier(n_estimators=200, max_depth=14, min_samples_leaf=5, n_jobs=n_workers(),
                                    class_weight="balanced", random_state=0)
        rf.fit(feats[tr], labels[tr].astype(int))
        pred_te = rf.predict(feats[te])
        kappa = float(cohen_kappa_score(labels[te].astype(int), pred_te))
        acc = float((pred_te == labels[te].astype(int)).mean())
        cm = confusion_matrix(labels[te].astype(int), pred_te, labels=list(rf.classes_)).tolist()
        p_all = np.full((valid.size, len(rf.classes_)), np.nan, "float32")
        vi = np.flatnonzero(valid)
        for s in range(0, vi.size, 2_000_000):
            p_all[vi[s:s + 2_000_000]] = rf.predict_proba(feats[vi[s:s + 2_000_000]])
        sev.ravel()[vi] = np.asarray(rf.classes_)[np.nanargmax(p_all[vi], axis=1)]
        prob.ravel()[vi] = np.nanmax(p_all[vi], axis=1)
        metrics["severity"] = dict(method="random forest on NISAR change, labels from Sentinel-2 dNBR",
                                   holdout_accuracy=acc, kappa=kappa, confusion=cm,
                                   classes=[CLASSES[int(c)] for c in rf.classes_],
                                   feature_importance=dict(zip(["dHV", "dHH", "dHV-dHH", "HV_pre", "HH_pre"],
                                                               rf.feature_importances_.round(3).tolist())))
        LOG.info("Severity RF: accuracy %.2f, kappa %.2f (holdout n=%d)", acc, kappa, te.size)
    else:
        br = cfg["severity"]["dhv_breaks_db"]          # more negative = more severe
        c = np.zeros(grid.shape, "float32")
        for k, thr in enumerate(br, start=1):
            c[dhv <= thr] = k
        c[~np.isfinite(dhv)] = np.nan
        sev = c
        metrics["severity"] = dict(method="HV change thresholds (ASSUMPTION, no dNBR)", breaks_db=br)

    perim_p = path(cfg, "work", "grid", "perimeter.tif")
    if perim_p.exists():   # outside the official perimeter (+ ~500 m) nothing is burned
        from scipy.ndimage import binary_dilation
        per = read_raster(perim_p) > 0
        per = binary_dilation(per, iterations=max(1, int(500 / grid.res)))
        sev[~per & np.isfinite(sev)] = 0
    else:   # drop isolated speckle pixels: keep burned clusters of >= 1 ha
        from scipy.ndimage import label
        lab, n = label(np.nan_to_num(sev) >= 1)
        sizes = np.bincount(lab.ravel())
        small = sizes < max(2, int(1e4 / grid.res ** 2))
        small[0] = False
        sev[small[lab]] = 0

    write_raster(path(cfg, "work", "severity", "class.tif"), np.nan_to_num(sev, nan=255).astype("uint8"), grid,
                 nodata=255, dtype="uint8", desc="0 unburned, 1 low, 2 moderate, 3 high")
    write_raster(path(cfg, "work", "severity", "prob.tif"), prob, grid)
    px_ha = grid.res ** 2 / 1e4
    metrics["burned_ha"] = {CLASSES[c]: float((sev == c).sum() * px_ha) for c in range(1, 4)}
    write_json(path(cfg, "work", "severity", "metrics.json"), metrics, indent=1)
    LOG.info("Burned area (ha): %s", {k: round(v) for k, v in metrics["burned_ha"].items()})


if __name__ == "__main__":
    main()
